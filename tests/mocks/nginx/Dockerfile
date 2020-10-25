FROM nginx@sha256:ed7f815851b5299f616220a63edac69a4cc200e7f536a56e421988da82e44ed8
COPY index.html /usr/share/nginx/html/index.html
COPY cert.crt /etc/ssl/cert.crt
COPY cert.key /etc/ssl/cert.key
COPY default.conf /etc/nginx/conf.d/default.conf
