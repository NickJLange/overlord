LUNARBEACON_HOST ?= lunarBeacon
REPO_PATH ?= /data/infrastructure/overlord
DEPLOY_PATH ?= $(REPO_PATH)/internal_cert_management
IMAGE_NAME ?= cert-renewal
IMAGE_TAG ?= latest

.PHONY: all refresh-certs vault vault-force certs certs-force certs-linux certs-linux-force certs-udm certs-udm-force push-from-files build quadlet-install clean

all: refresh-certs vault certs
	@echo "Certificate cycle complete"

refresh-certs:
	@echo "Running certificate refresh..."
	scripts/lego.sh

vault:
	@echo "Uploading certificates to Vault..."
	scripts/upload-to-vault.sh

vault-force:
	@echo "Uploading certificates to Vault (with --force flag)..."
	scripts/upload-to-vault.sh --force

certs: certs-linux certs-udm
	@echo "All endpoint updates complete"

certs-force: certs-linux-force certs-udm-force
	@echo "All endpoint updates complete"

certs-linux:
	@echo "Updating Linux endpoints..."
	scripts/update_linux.sh

certs-linux-force:
	@echo "Updating Linux endpoints (with --force flag)..."
	scripts/update_linux.sh --force

certs-udm:
	@echo "Updating UDM devices..."
	scripts/update_udm.sh

certs-udm-force:
	@echo "Updating UDM devices (with --force flag)..."
	scripts/update_udm.sh --force

push-from-files:
	@echo "Pushing certs from local files to Vault host..."
	scripts/push_from_files.sh

build:
	@echo "Building $(IMAGE_NAME):$(IMAGE_TAG) on $(LUNARBEACON_HOST)..."
	ssh $(LUNARBEACON_HOST) "podman build --build-arg LEGO_ARCH=amd64 -t $(IMAGE_NAME):$(IMAGE_TAG) $(DEPLOY_PATH)/internal_cert_management"
	@echo "Build complete."

quadlet-install:
	@echo "Installing Quadlet units on $(LUNARBEACON_HOST) (rootless, user njl)..."
	ssh $(LUNARBEACON_HOST) "[ -d $(REPO_PATH)/.git ] || git clone git@github.com:NickJLange/overlord.git $(REPO_PATH)"
	ssh $(LUNARBEACON_HOST) " \
		mkdir -p ~/.config/containers/systemd && \
		cp $(DEPLOY_PATH)/systemd/cert-renewal.container ~/.config/containers/systemd/ && \
		cp $(DEPLOY_PATH)/systemd/cert-renewal.timer ~/.config/containers/systemd/ && \
		systemctl --user daemon-reload && \
		systemctl --user enable --now cert-renewal.timer && \
		loginctl enable-linger njl"
	@echo "Quadlet installed. Build the image with 'make build', then scp secrets separately."

clean:
	@echo "Cleaning up...Nothing!"
