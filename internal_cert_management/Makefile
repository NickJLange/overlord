
.PHONY: all refresh-certs vault vault-force certs certs-force
all: clean

.PHONY: refresh-certs
refresh-certs:
	@echo "Running certificate refresh..."
	scripts/lego.sh

vault:
	@echo "Uploading certificates to Vault..."
	scripts/upload-to-vault.sh

vault-force:
	@echo "Uploading certificates to Vault (with --force flag)..."
	scripts/upload-to-vault.sh --force

certs:
	@echo "Updating Endpoints..."
	scripts/update_endpoints.sh

certs-force:
	@echo "Updating Endpoints (with --force flag)..."
	scripts/update_endpoints.sh --force

.PHONY: clean
clean:
	@echo "Cleaning up...Nothing!"
