
.PHONY: all refresh-certs vault certs
all: clean

.PHONY: refresh-certs
refresh-certs:
	@echo "Running certificate refresh..."
	scripts/lego.sh

vault:
	@echo "Uploading certificates to Vault..."
	scripts/upload_vault.sh

certs:
	@echo "Updating Endpoints..."
	scripts/update_endpoints.sh

.PHONY: clean
clean:
	@echo "Cleaning up...Nothng!"
