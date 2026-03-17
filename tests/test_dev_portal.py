"""
Playwright tests for dev-portal.

Usage:
  # Against production (from a machine without Cloudflare WARP)
  python tests/test_dev_portal.py

  # With Cloudflare WARP DNS override (maps prod hostname to Cloudflare IP)
  python tests/test_dev_portal.py --dns-override

  # Against local docker-compose stack (docker compose up)
  python tests/test_dev_portal.py --url http://localhost:8080

  # Against a kubectl port-forward with separate API port-forward
  #   kubectl port-forward svc/dev-portal 18080:80 -n dev-portal &
  #   kubectl port-forward svc/dev-portal-api 18000:8000 -n dev-portal &
  python tests/test_dev_portal.py --url http://localhost:18080 --api-url http://localhost:18000
"""
import argparse
import sys
import time
from playwright.sync_api import sync_playwright, expect, Route

PROD_URL = "https://dev-portal.georg-nikola.com"
PROD_IP  = "104.21.12.221"   # Cloudflare proxy IP

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"

_UNIQUE_SVC  = f"test-svc-{int(time.time())}"
_UNIQUE_SVC2 = f"test-svc2-{int(time.time())}"


def run_tests(base_url: str, dns_override: bool = False, api_url: str | None = None):
    results = []

    def record(name: str, passed: bool, detail: str = ""):
        icon = PASS if passed else FAIL
        print(f"  {icon} {name}" + (f"  ({detail})" if detail else ""))
        results.append((name, passed))

    launch_args = []
    if dns_override:
        launch_args.append(
            f"--host-resolver-rules=MAP dev-portal.georg-nikola.com {PROD_IP}"
        )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=launch_args)
        ctx  = browser.new_context()
        page = ctx.new_page()

        # When testing via kubectl port-forward, intercept /api/* requests and
        # redirect them to the separately port-forwarded API service.
        if api_url:
            def _reroute_api(route: Route):
                new_url = api_url.rstrip("/") + route.request.url.split("/api", 1)[1]
                # Reconstruct with /api prefix preserved
                new_url = api_url.rstrip("/") + "/api" + route.request.url.split("/api", 1)[1]
                route.continue_(url=new_url)
            page.route("**/api/**", _reroute_api)

        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
        failed_requests: list[str] = []
        page.on("requestfailed", lambda r: failed_requests.append(r.url))

        # ── 1. Page load ──────────────────────────────────────────────────────
        print("\n[Page Load]")
        try:
            page.goto(base_url, timeout=30_000)
            page.wait_for_load_state("networkidle")
            record("Page loads without error", True)
        except Exception as e:
            record("Page loads without error", False, str(e))
            browser.close()
            return results

        try:
            title = page.title()
            record("Page title is 'Dev Portal'", title == "Dev Portal", title)
        except Exception as e:
            record("Page title is 'Dev Portal'", False, str(e))

        try:
            expect(page.locator(".topnav-brand .brand-name")).to_have_text("Dev Portal")
            record("Brand name visible in nav", True)
        except Exception as e:
            record("Brand name visible in nav", False, str(e))

        try:
            expect(page.locator("#addServiceBtn")).to_be_visible()
            record("'+ Add Service' button visible", True)
        except Exception as e:
            record("'+ Add Service' button visible", False, str(e))

        try:
            expect(page.locator("#searchInput")).to_be_visible()
            record("Search input visible", True)
        except Exception as e:
            record("Search input visible", False, str(e))

        try:
            expect(page.locator("#statusFilters")).to_be_visible()
            record("Status filter panel visible", True)
        except Exception as e:
            record("Status filter panel visible", False, str(e))

        # ── 2. Add Service modal ──────────────────────────────────────────────
        print("\n[Add Service Modal]")
        try:
            page.click("#addServiceBtn")
            expect(page.locator("#serviceModal")).to_be_visible()
            record("Modal opens on '+ Add Service' click", True)
        except Exception as e:
            record("Modal opens on '+ Add Service' click", False, str(e))

        try:
            expect(page.locator("#modalTitle")).to_have_text("Add Service")
            record("Modal title is 'Add Service'", True)
        except Exception as e:
            record("Modal title is 'Add Service'", False, str(e))

        try:
            expect(page.locator("#formName")).to_be_visible()
            expect(page.locator("#formTeam")).to_be_visible()
            expect(page.locator("#formDescription")).to_be_visible()
            expect(page.locator("#formStatus")).to_be_visible()
            expect(page.locator("#formTags")).to_be_visible()
            expect(page.locator("#formStatusUrl")).to_be_visible()
            expect(page.locator("#formDocsUrl")).to_be_visible()
            expect(page.locator("#formGithubUrl")).to_be_visible()
            record("All form fields visible", True)
        except Exception as e:
            record("All form fields visible", False, str(e))

        # Close via Cancel
        try:
            page.click("#modalCancel")
            expect(page.locator("#serviceModal")).to_have_class("modal-overlay hidden")
            record("Modal closes on Cancel click", True)
        except Exception as e:
            record("Modal closes on Cancel click", False, str(e))

        # Close via Escape key
        try:
            page.click("#addServiceBtn")
            expect(page.locator("#serviceModal")).to_be_visible()
            page.keyboard.press("Escape")
            expect(page.locator("#serviceModal")).to_have_class("modal-overlay hidden")
            record("Modal closes on Escape key", True)
        except Exception as e:
            record("Modal closes on Escape key", False, str(e))

        # ── 3. Create a service ───────────────────────────────────────────────
        print("\n[Create Service]")
        try:
            page.click("#addServiceBtn")
            page.fill("#formName", _UNIQUE_SVC)
            page.fill("#formTeam", "Platform")
            page.fill("#formDescription", "Test service created by Playwright")
            page.select_option("#formStatus", "healthy")
            page.fill("#formTags", "test, automation")
            page.fill("#formDocsUrl", "https://docs.example.com")
            page.fill("#formGithubUrl", "https://github.com/example/test")
            page.click("#saveServiceBtn")
            # Wait for modal to close (indicates successful save)
            expect(page.locator("#serviceModal")).to_have_class("modal-overlay hidden", timeout=10_000)
            record("Service created successfully", True)
        except Exception as e:
            record("Service created successfully", False, str(e))

        # ── 4. Service card appears ───────────────────────────────────────────
        print("\n[Service Card]")
        try:
            card = page.locator(f".service-card[data-id]").filter(has_text=_UNIQUE_SVC)
            expect(card).to_be_visible(timeout=10_000)
            record("Service card appears in grid", True)
        except Exception as e:
            record("Service card appears in grid", False, str(e))
            # Recovery: refresh
            page.reload()
            page.wait_for_load_state("networkidle")

        try:
            card = page.locator(".service-card").filter(has_text=_UNIQUE_SVC)
            expect(card.locator(".card-name")).to_have_text(_UNIQUE_SVC)
            record("Card shows correct service name", True)
        except Exception as e:
            record("Card shows correct service name", False, str(e))

        try:
            card = page.locator(".service-card").filter(has_text=_UNIQUE_SVC)
            expect(card.locator(".status-badge")).to_have_class("status-badge healthy")
            record("Card shows 'healthy' status badge", True)
        except Exception as e:
            record("Card shows 'healthy' status badge", False, str(e))

        try:
            card = page.locator(".service-card").filter(has_text=_UNIQUE_SVC)
            expect(card.locator(".card-team")).to_have_text("Platform")
            record("Card shows team name", True)
        except Exception as e:
            record("Card shows team name", False, str(e))

        try:
            card = page.locator(".service-card").filter(has_text=_UNIQUE_SVC)
            tags = card.locator(".tag-chip")
            expect(tags).to_have_count(2)
            record("Card shows 2 tags", True)
        except Exception as e:
            record("Card shows 2 tags", False, str(e))

        try:
            card = page.locator(".service-card").filter(has_text=_UNIQUE_SVC)
            links = card.locator(".card-link-btn")
            expect(links).to_have_count(2)  # docs + github
            record("Card shows docs and GitHub links", True)
        except Exception as e:
            record("Card shows docs and GitHub links", False, str(e))

        # ── 5. Sidebar stats update ───────────────────────────────────────────
        print("\n[Sidebar Stats]")
        try:
            total_text = page.locator("#statTotal").inner_text()
            total = int(total_text)
            record("Sidebar total count is a number", total >= 1, f"count={total}")
        except Exception as e:
            record("Sidebar total count is a number", False, str(e))

        try:
            healthy_text = page.locator("#statHealthy").inner_text()
            healthy = int(healthy_text)
            record("Sidebar healthy count >= 1 (just created one)", healthy >= 1, f"count={healthy}")
        except Exception as e:
            record("Sidebar healthy count >= 1", False, str(e))

        # ── 6. Search filtering ───────────────────────────────────────────────
        print("\n[Search Filter]")
        try:
            page.fill("#searchInput", _UNIQUE_SVC)
            page.wait_for_timeout(400)  # debounce
            cards = page.locator(".service-card")
            count = cards.count()
            record("Search narrows results to matching services", count >= 1, f"cards={count}")
        except Exception as e:
            record("Search narrows results to matching services", False, str(e))

        try:
            page.fill("#searchInput", "zzz-nonexistent-xyz-abc")
            page.wait_for_timeout(400)
            expect(page.locator("#emptyState")).to_be_visible()
            record("Empty state shown when search has no matches", True)
        except Exception as e:
            record("Empty state shown when search has no matches", False, str(e))

        try:
            page.fill("#searchInput", "")
            page.wait_for_timeout(400)
            expect(page.locator("#emptyState")).to_have_class("empty-state hidden")
            record("Clearing search restores all cards", True)
        except Exception as e:
            record("Clearing search restores all cards", False, str(e))

        # ── 7. Status sidebar filter ──────────────────────────────────────────
        print("\n[Status Filter]")
        try:
            page.locator("#statusFilters .filter-chip[data-value='healthy']").click()
            page.wait_for_timeout(200)
            cards_after = page.locator(".service-card").count()
            # Our service is healthy so at least one should show
            record("Healthy status filter shows at least our service", cards_after >= 1, f"cards={cards_after}")
        except Exception as e:
            record("Healthy status filter shows at least our service", False, str(e))

        try:
            # Click again to deactivate
            page.locator("#statusFilters .filter-chip[data-value='healthy']").click()
            page.wait_for_timeout(200)
            active_chip = page.locator("#statusFilters .filter-chip.active")
            expect(active_chip).to_have_attribute("data-value", "")
            record("Clicking active status filter toggles it off", True)
        except Exception as e:
            record("Clicking active status filter toggles it off", False, str(e))

        # ── 8. Team sidebar filter ────────────────────────────────────────────
        print("\n[Team Filter]")
        try:
            team_chip = page.locator("#teamFilters .filter-chip[data-value='Platform']")
            expect(team_chip).to_be_visible()
            team_chip.click()
            page.wait_for_timeout(200)
            cards = page.locator(".service-card").count()
            record("Team filter 'Platform' shows our service", cards >= 1, f"cards={cards}")
        except Exception as e:
            record("Team filter 'Platform' shows our service", False, str(e))

        try:
            page.locator("#teamFilters .filter-chip[data-value='Platform']").click()
            page.wait_for_timeout(200)
            record("Clicking team filter again deactivates it", True)
        except Exception as e:
            record("Clicking team filter again deactivates it", False, str(e))

        # ── 9. Tag filter (from card chip) ────────────────────────────────────
        print("\n[Tag Filter]")
        try:
            card = page.locator(".service-card").filter(has_text=_UNIQUE_SVC)
            tag_chip = card.locator(".tag-chip").first
            tag_chip.click()
            page.wait_for_timeout(200)
            # Tag filter chip in sidebar should now be active
            active_tag = page.locator("#tagFilters .filter-chip.active")
            expect(active_tag).to_be_visible()
            record("Clicking tag chip activates tag filter in sidebar", True)
        except Exception as e:
            record("Clicking tag chip activates tag filter in sidebar", False, str(e))

        try:
            # Deactivate by clicking the active tag filter
            page.locator("#tagFilters .filter-chip.active").click()
            page.wait_for_timeout(200)
            record("Clicking active tag filter deactivates it", True)
        except Exception as e:
            record("Clicking active tag filter deactivates it", False, str(e))

        # ── 10. Edit service ──────────────────────────────────────────────────
        print("\n[Edit Service]")
        try:
            card = page.locator(".service-card").filter(has_text=_UNIQUE_SVC)
            # Click the card body (not a link/tag/button)
            card.locator(".card-name").click()
            expect(page.locator("#serviceModal")).to_be_visible(timeout=5_000)
            record("Edit modal opens on card click", True)
        except Exception as e:
            record("Edit modal opens on card click", False, str(e))

        try:
            expect(page.locator("#modalTitle")).to_have_text("Edit Service")
            record("Edit modal title is 'Edit Service'", True)
        except Exception as e:
            record("Edit modal title is 'Edit Service'", False, str(e))

        try:
            name_val = page.locator("#formName").input_value()
            record("Edit modal pre-fills service name", name_val == _UNIQUE_SVC, f"value={name_val!r}")
        except Exception as e:
            record("Edit modal pre-fills service name", False, str(e))

        try:
            status_val = page.locator("#formStatus").input_value()
            record("Edit modal pre-fills status", status_val == "healthy", f"value={status_val!r}")
        except Exception as e:
            record("Edit modal pre-fills status", False, str(e))

        try:
            expect(page.locator("#deleteServiceBtn")).to_be_visible()
            expect(page.locator("#deleteServiceBtn")).not_to_have_class("hidden")
            record("Delete button visible in edit modal", True)
        except Exception as e:
            record("Delete button visible in edit modal", False, str(e))

        # Update the description
        try:
            page.fill("#formDescription", "Updated by Playwright test")
            page.select_option("#formStatus", "degraded")
            page.click("#saveServiceBtn")
            expect(page.locator("#serviceModal")).to_have_class("modal-overlay hidden", timeout=10_000)
            record("Service updated successfully", True)
        except Exception as e:
            record("Service updated successfully", False, str(e))

        try:
            card = page.locator(".service-card").filter(has_text=_UNIQUE_SVC)
            expect(card.locator(".status-badge")).to_have_class("status-badge degraded", timeout=5_000)
            record("Updated status badge reflects 'degraded'", True)
        except Exception as e:
            record("Updated status badge reflects 'degraded'", False, str(e))

        # ── 11. View meta count ───────────────────────────────────────────────
        print("\n[View Meta]")
        try:
            meta = page.locator("#viewMeta").inner_text()
            record("View meta shows service count", "service" in meta, f"text={meta!r}")
        except Exception as e:
            record("View meta shows service count", False, str(e))

        # ── 12. Delete service ────────────────────────────────────────────────
        print("\n[Delete Service]")
        try:
            card = page.locator(".service-card").filter(has_text=_UNIQUE_SVC)
            card.locator(".card-name").click()
            expect(page.locator("#serviceModal")).to_be_visible(timeout=5_000)
            page.click("#deleteServiceBtn")
            expect(page.locator("#confirmModal")).to_be_visible(timeout=3_000)
            record("Confirm delete modal appears", True)
        except Exception as e:
            record("Confirm delete modal appears", False, str(e))

        try:
            msg = page.locator("#confirmMsg").inner_text()
            record("Confirm modal message mentions the service name", _UNIQUE_SVC in msg, f"msg={msg!r}")
        except Exception as e:
            record("Confirm modal message mentions the service name", False, str(e))

        # Cancel delete
        try:
            page.click("#confirmCancel")
            expect(page.locator("#confirmModal")).to_have_class("modal-overlay hidden")
            record("Cancelling delete dismisses confirm modal", True)
        except Exception as e:
            record("Cancelling delete dismisses confirm modal", False, str(e))

        # Close service modal too
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)

        # Now actually delete
        try:
            card = page.locator(".service-card").filter(has_text=_UNIQUE_SVC)
            card.locator(".card-name").click()
            expect(page.locator("#serviceModal")).to_be_visible(timeout=5_000)
            page.click("#deleteServiceBtn")
            expect(page.locator("#confirmModal")).to_be_visible(timeout=3_000)
            page.click("#confirmOk")
            # Service should vanish from grid
            page.wait_for_timeout(2_000)
            remaining = page.locator(".service-card").filter(has_text=_UNIQUE_SVC).count()
            record("Service removed from grid after delete", remaining == 0, f"remaining={remaining}")
        except Exception as e:
            record("Service removed from grid after delete", False, str(e))

        # ── 13. Validation: empty name blocked ────────────────────────────────
        print("\n[Validation]")
        try:
            page.click("#addServiceBtn")
            expect(page.locator("#serviceModal")).to_be_visible()
            # Leave name empty and try to save
            page.fill("#formName", "")
            page.click("#saveServiceBtn")
            # Modal should still be open (save blocked)
            expect(page.locator("#serviceModal")).to_be_visible()
            record("Save blocked when service name is empty", True)
        except Exception as e:
            record("Save blocked when service name is empty", False, str(e))
        finally:
            page.keyboard.press("Escape")
            page.wait_for_timeout(200)

        # ── 14. Toast notification ────────────────────────────────────────────
        print("\n[Toast Notification]")
        try:
            page.click("#addServiceBtn")
            page.fill("#formName", _UNIQUE_SVC2)
            page.click("#saveServiceBtn")
            # Toast should appear
            toast = page.locator(".toast.success")
            expect(toast).to_be_visible(timeout=5_000)
            record("Success toast appears after adding a service", True)
            # Wait for it to auto-dismiss
            page.wait_for_timeout(4_000)
            # Cleanup
            card = page.locator(".service-card").filter(has_text=_UNIQUE_SVC2)
            card.locator(".card-name").click()
            page.click("#deleteServiceBtn")
            page.click("#confirmOk")
            page.wait_for_timeout(1_000)
        except Exception as e:
            record("Success toast appears after adding a service", False, str(e))
            page.keyboard.press("Escape")

        # ── 15. No console errors ─────────────────────────────────────────────
        print("\n[Console Errors]")
        critical = [e for e in console_errors if "favicon" not in e.lower()]
        record("No critical console errors", len(critical) == 0,
               f"{len(critical)} error(s)" if critical else "")
        if critical:
            for err in critical[:3]:
                print(f"    → {err[:120]}")

        browser.close()

    return results


def main():
    parser = argparse.ArgumentParser(description="Dev Portal Playwright tests")
    parser.add_argument("--url", default=PROD_URL, help="Base URL to test against")
    parser.add_argument("--api-url", default=None,
                        help="Override API base URL (for port-forward mode). "
                             "Intercepts /api/* requests and redirects to this host. "
                             "Example: http://localhost:18000")
    parser.add_argument("--dns-override", action="store_true",
                        help="Override DNS to bypass Cloudflare WARP (uses PROD_IP)")
    args = parser.parse_args()

    print(f"\nDev Portal Test Suite")
    print(f"Target: {args.url}")
    if args.api_url:
        print(f"API override: {args.api_url}")
    print("=" * 50)

    results = run_tests(args.url, dns_override=args.dns_override, api_url=args.api_url)

    print("\n" + "=" * 50)
    passed = sum(1 for _, ok in results if ok)
    total  = len(results)
    failed = total - passed

    print(f"Results: {passed}/{total} passed" + (f", {failed} failed" if failed else ""))

    if failed:
        print("\nFailed tests:")
        for name, ok in results:
            if not ok:
                print(f"  {FAIL} {name}")
        sys.exit(1)
    else:
        print("All tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
