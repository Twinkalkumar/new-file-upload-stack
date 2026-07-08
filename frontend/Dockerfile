FROM nginx:alpine

# Copy HTML files
COPY login.html /usr/share/nginx/html/
COPY signup.html /usr/share/nginx/html/
COPY upload.html /usr/share/nginx/html/

# Copy custom nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]