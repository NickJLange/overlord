-include .env
export

# Required — set in .env: DEPLOY_HOST, DEPLOY_USER, REPO_PATH
DEPLOY_PATH ?= $(REPO_PATH)/internal_cert_management
IMAGE_NAME ?= cert-renewal
IMAGE_TAG ?= latest
ANSIBLE_SUBMODULE ?= $(abspath $(CURDIR)/../private-smart-home-ansible)

.PHONY: all refresh-certs vault vault-force certs certs-force certs-linux certs-linux-force certs-udm certs-udm-force push-from-files build quadlet-install deploy-config clean _require-deploy-vars

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

certs: certs-linux
	@echo "All endpoint updates complete"

certs-force: certs-linux-force
	@echo "All endpoint updates complete"

certs-linux:
	@echo "Updating endpoints (Linux + UDM)..."
	scripts/update_endpoints.sh

certs-linux-force:
	@echo "Updating endpoints (Linux + UDM, --force)..."
	scripts/update_endpoints.sh --force

certs-udm:
	@echo "UDM updates are handled by update_endpoints.sh (see certs-linux)"
	scripts/update_endpoints.sh

certs-udm-force:
	@echo "UDM updates are handled by update_endpoints.sh (see certs-linux-force)"
	scripts/update_endpoints.sh --force

push-from-files:
	@echo "Pushing certs from local files to Vault host..."
	scripts/push_from_files.sh

_require-deploy-vars:
	@test -n "$(DEPLOY_HOST)" || (echo "ERROR: DEPLOY_HOST not set in .env"; exit 1)
	@test -n "$(DEPLOY_USER)" || (echo "ERROR: DEPLOY_USER not set in .env"; exit 1)
	@test -n "$(REPO_PATH)"   || (echo "ERROR: REPO_PATH not set in .env"; exit 1)

build: _require-deploy-vars
	@echo "Building $(IMAGE_NAME):$(IMAGE_TAG) on $(DEPLOY_HOST)..."
	ssh $(DEPLOY_HOST) "podman build --build-arg LEGO_ARCH=amd64 -t $(IMAGE_NAME):$(IMAGE_TAG) $(DEPLOY_PATH)"
	@echo "Build complete."

quadlet-install: _require-deploy-vars
	@echo "Installing Quadlet units on $(DEPLOY_HOST) (rootless, user $(DEPLOY_USER))..."
	ssh $(DEPLOY_HOST) "[ -d $(REPO_PATH)/.git ] || git clone https://github.com/NickJLange/overlord.git $(REPO_PATH)"
	ssh $(DEPLOY_HOST) " \
		mkdir -p ~/.config/containers/systemd ~/.config/systemd/user && \
		REPO_PATH=$(REPO_PATH) DEPLOY_USER=$(DEPLOY_USER) envsubst < $(DEPLOY_PATH)/systemd/cert-renewal.container.tmpl \
			> ~/.config/containers/systemd/cert-renewal.container && \
		cp $(DEPLOY_PATH)/systemd/cert-renewal.timer ~/.config/systemd/user/ && \
		systemctl --user daemon-reload && \
		systemctl --user enable --now cert-renewal.timer && \
		loginctl enable-linger $(DEPLOY_USER)"
	@echo "Quadlet installed. Build the image with 'make build', then scp secrets separately."

deploy-config: _require-deploy-vars
	@echo "Deploying ansible config files to $(DEPLOY_HOST)..."
	ssh $(DEPLOY_HOST) "mkdir -p $(REPO_PATH)/internal_cert_management/etc"
	scp $(ANSIBLE_SUBMODULE)/ansible.cfg \
		$(DEPLOY_HOST):$(REPO_PATH)/internal_cert_management/etc/ansible.cfg
	scp $(ANSIBLE_SUBMODULE)/non_tasmota_hosts.inventory \
		$(DEPLOY_HOST):$(REPO_PATH)/internal_cert_management/etc/non_tasmota_hosts.inventory
	@echo "Config deployed. Run quadlet-install if the container unit changed."

clean:
	@echo "Cleaning up...Nothing!"
