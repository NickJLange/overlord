LUNARBEACON_HOST ?= lunarBeacon
DEPLOY_PATH ?= /data/infrastructure/cert_management

.PHONY: all refresh-certs vault vault-force certs certs-force certs-linux certs-linux-force certs-udm certs-udm-force push-from-files deploy clean

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

deploy:
	@echo "Deploying cert management to $(LUNARBEACON_HOST):$(DEPLOY_PATH)..."
	rsync -av --exclude='.env' --exclude='lego-data/' --exclude='etc/' \
		./ $(LUNARBEACON_HOST):$(DEPLOY_PATH)/
	ssh $(LUNARBEACON_HOST) " \
		sudo cp $(DEPLOY_PATH)/systemd/cert-renewal.service /etc/systemd/system/ && \
		sudo cp $(DEPLOY_PATH)/systemd/cert-renewal.timer /etc/systemd/system/ && \
		sudo systemctl daemon-reload && \
		sudo systemctl enable --now cert-renewal.timer"
	@echo "Deploy complete. Secrets must be scp'd separately."

clean:
	@echo "Cleaning up...Nothing!"
