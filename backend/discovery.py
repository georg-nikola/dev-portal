from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from kubernetes_asyncio import client as k8s_client
from kubernetes_asyncio.client import ApiClient, Configuration
from kubernetes_asyncio.config import load_incluster_config
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from encryption import decrypt_value
from models import ClusterConfig, Service
from schemas_cluster import DiscoveredWorkload, DiscoveryResult, DiscoveryResultItem

logger = logging.getLogger(__name__)


async def build_k8s_client(cluster: ClusterConfig) -> ApiClient:
    """Build a kubernetes-asyncio ApiClient from a ClusterConfig."""
    if cluster.is_in_cluster:
        load_incluster_config()
        return ApiClient()

    config = Configuration()
    config.host = cluster.api_server_url
    config.verify_ssl = False  # internal clusters often use self-signed certs

    if cluster.encrypted_token:
        token = decrypt_value(cluster.encrypted_token)
        config.api_key = {"authorization": f"Bearer {token}"}
    elif cluster.encrypted_kubeconfig:
        # For kubeconfig, load via temp file approach
        import tempfile
        import yaml
        from kubernetes_asyncio.config import load_kube_config

        kubeconfig_yaml = decrypt_value(cluster.encrypted_kubeconfig)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(kubeconfig_yaml)
            f.flush()
            await load_kube_config(config_file=f.name)
        return ApiClient()

    return ApiClient(configuration=config)


async def discover_workloads(
    api_client: ApiClient,
    namespace_filter: Optional[str] = None,
) -> list[DiscoveredWorkload]:
    """List Deployments and StatefulSets from a Kubernetes cluster."""
    workloads: list[DiscoveredWorkload] = []
    apps_v1 = k8s_client.AppsV1Api(api_client)

    namespaces = (
        [ns.strip() for ns in namespace_filter.split(",") if ns.strip()]
        if namespace_filter
        else None
    )

    try:
        # Discover Deployments
        if namespaces:
            deploys = []
            for ns in namespaces:
                resp = await apps_v1.list_namespaced_deployment(ns)
                deploys.extend(resp.items)
        else:
            resp = await apps_v1.list_deployment_for_all_namespaces()
            deploys = resp.items

        for d in deploys:
            workloads.append(_parse_workload(d, "Deployment"))

        # Discover StatefulSets
        if namespaces:
            statefulsets = []
            for ns in namespaces:
                resp = await apps_v1.list_namespaced_stateful_set(ns)
                statefulsets.extend(resp.items)
        else:
            resp = await apps_v1.list_stateful_set_for_all_namespaces()
            statefulsets = resp.items

        for ss in statefulsets:
            workloads.append(_parse_workload(ss, "StatefulSet"))

    finally:
        await api_client.close()

    return workloads


def _parse_workload(obj, kind: str) -> DiscoveredWorkload:
    """Extract a DiscoveredWorkload from a k8s Deployment or StatefulSet."""
    name = obj.metadata.name
    namespace = obj.metadata.namespace
    labels = dict(obj.metadata.labels or {})

    desired = obj.spec.replicas or 0
    ready = 0
    if obj.status:
        ready = getattr(obj.status, "ready_replicas", 0) or 0

    if desired == 0:
        status = "unknown"
    elif ready == desired:
        status = "healthy"
    elif ready > 0:
        status = "degraded"
    else:
        status = "down"

    # Try to extract health check URL from first container's readiness probe
    health_url = _extract_health_url(obj, namespace)

    return DiscoveredWorkload(
        name=name,
        namespace=namespace,
        kind=kind,
        status=status,
        replicas_ready=ready,
        replicas_desired=desired,
        labels=labels,
        health_check_url=health_url,
    )


def _extract_health_url(obj, namespace: str) -> Optional[str]:
    """Try to extract an HTTP health check URL from the readiness probe."""
    try:
        containers = obj.spec.template.spec.containers
        if not containers:
            return None
        probe = containers[0].readiness_probe
        if not probe or not probe.http_get:
            return None
        port = probe.http_get.port
        path = probe.http_get.path or "/"
        scheme = (probe.http_get.scheme or "HTTP").lower()
        svc_name = obj.metadata.name
        return f"{scheme}://{svc_name}.{namespace}.svc.cluster.local:{port}{path}"
    except (AttributeError, IndexError):
        return None


async def sync_discovered_services(
    db: AsyncSession,
    owner_id: uuid.UUID,
    cluster_id: uuid.UUID,
    cluster_name: str,
    workloads: list[DiscoveredWorkload],
) -> DiscoveryResult:
    """Create or update services from discovered workloads."""
    results: list[DiscoveryResultItem] = []
    created = 0
    updated = 0
    unchanged = 0

    for w in workloads:
        # Use namespace-qualified name to avoid collisions
        svc_name = f"{w.name}" if not _has_name_collision(w.name, workloads) else f"{w.name}-{w.namespace}"

        # Check if we already discovered this service for this cluster
        result = await db.execute(
            select(Service).where(
                Service.owner_id == owner_id,
                Service.cluster_id == cluster_id,
                Service.name == svc_name,
            )
        )
        existing = result.scalar_one_or_none()

        tags = _build_tags(w)

        if existing:
            # Check if anything changed
            changed = False
            if existing.status != w.status:
                existing.status = w.status
                changed = True
            if existing.team != w.namespace:
                existing.team = w.namespace
                changed = True
            if set(existing.tags or []) != set(tags):
                existing.tags = tags
                changed = True
            if existing.status_url != w.health_check_url:
                existing.status_url = w.health_check_url
                changed = True

            if changed:
                existing.updated_at = datetime.now(timezone.utc)
                updated += 1
                results.append(DiscoveryResultItem(name=svc_name, action="updated"))
            else:
                unchanged += 1
                results.append(DiscoveryResultItem(name=svc_name, action="unchanged"))
        else:
            # Also check if user has a manually-created service with this name
            manual = await db.execute(
                select(Service).where(
                    Service.owner_id == owner_id,
                    Service.name == svc_name,
                    Service.cluster_id.is_(None),
                )
            )
            if manual.scalar_one_or_none():
                # Don't overwrite manually created services
                unchanged += 1
                results.append(DiscoveryResultItem(name=svc_name, action="unchanged"))
                continue

            svc = Service(
                owner_id=owner_id,
                cluster_id=cluster_id,
                name=svc_name,
                description=f"{w.kind} in {w.namespace} ({w.replicas_ready}/{w.replicas_desired} ready)",
                team=w.namespace,
                status=w.status,
                status_url=w.health_check_url,
                tags=tags,
            )
            db.add(svc)
            created += 1
            results.append(DiscoveryResultItem(name=svc_name, action="created"))

    await db.commit()

    return DiscoveryResult(
        cluster_name=cluster_name,
        total_workloads=len(workloads),
        created=created,
        updated=updated,
        unchanged=unchanged,
        items=results,
    )


def _has_name_collision(name: str, workloads: list[DiscoveredWorkload]) -> bool:
    """Check if a workload name appears in multiple namespaces."""
    count = sum(1 for w in workloads if w.name == name)
    return count > 1


def _build_tags(w: DiscoveredWorkload) -> list[str]:
    """Build tags from workload metadata."""
    tags = ["k8s", "discovered", w.namespace, w.kind.lower()]

    # Extract common k8s labels
    for key in ["app.kubernetes.io/component", "app.kubernetes.io/part-of"]:
        val = w.labels.get(key)
        if val:
            tags.append(val)

    return sorted(set(tags))
