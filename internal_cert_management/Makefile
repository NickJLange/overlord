.PHONY: all refresh-certs vault vault-force certs certs-force certs-linux certs-linux-force certs-udm certs-udm-force push-from-files clean

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

clean:
	@echo "Cleaning up...Nothing!"
