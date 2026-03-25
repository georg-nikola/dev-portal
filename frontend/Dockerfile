FROM nginx:stable-alpine3.23

RUN addgroup -g 101 -S nginx || true && \
    adduser -S -D -H -u 101 -h /var/cache/nginx -s /sbin/nologin -G nginx -g nginx nginx || true

RUN rm -rf /etc/nginx/conf.d/default.conf /usr/share/nginx/html/*

COPY nginx.conf /etc/nginx/nginx.conf

COPY index.html   /usr/share/nginx/html/index.html
COPY catalog.html /usr/share/nginx/html/catalog.html
COPY style.css    /usr/share/nginx/html/style.css
COPY app.js       /usr/share/nginx/html/app.js
COPY landing.js   /usr/share/nginx/html/landing.js
COPY login.html   /usr/share/nginx/html/login.html
COPY auth.js      /usr/share/nginx/html/auth.js

RUN echo "OK" > /usr/share/nginx/html/health

RUN chown -R nginx:nginx /usr/share/nginx/html && \
    chmod -R 755 /usr/share/nginx/html && \
    chown -R nginx:nginx /var/cache/nginx && \
    chown -R nginx:nginx /var/log/nginx && \
    touch /var/run/nginx.pid && \
    chown nginx:nginx /var/run/nginx.pid

USER nginx

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8080/health || exit 1

CMD ["nginx", "-g", "daemon off;"]
