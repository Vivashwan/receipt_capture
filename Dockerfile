# Production image: official ERPNext v15 + this app + Tesseract OCR.
#   docker build -t receipt-capture-erpnext .
ARG ERPNEXT_IMAGE=frappe/erpnext:v15.124.1
FROM ${ERPNEXT_IMAGE}

USER root
RUN apt-get update \
	&& apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng \
	&& rm -rf /var/lib/apt/lists/*

USER frappe
WORKDIR /home/frappe/frappe-bench
COPY --chown=frappe:root . apps/receipt_capture

# Install into the bench virtualenv. sites/ is a volume in the base image, so
# apps.txt is regenerated at startup by the compose "configurator" service
# (`ls -1 apps > sites/apps.txt`), the same pattern frappe_docker uses.
RUN ./env/bin/pip install --no-cache-dir -e apps/receipt_capture
