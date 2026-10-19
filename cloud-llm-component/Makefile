ARCHIVE_NAME ?= cloud-llm.tar.gz
INCLUDE_FILE ?= includes.txt
INCLUDED_FILES = $(foreach entry,$(shell cat $(INCLUDE_FILE)),$(wildcard $(entry)))

# Remote target (e.g. IBM Power 11 / ppc64le host)
SSH_TARGET ?= power-host
REMOTE_WORKDIR ?= ~/cloud-llm

# AI-Services Catalog Configuration
CATALOG_ID ?= llm--openai-cloud-llm
CATALOG_SERVER ?= https://catalog-ui.<cluster-domain-or-ip>.nip.io
CATALOG_USER ?= admin
CATALOG_PASSWORD_FILE ?= ~/aipw.txt

# Container Image Configuration (ppc64le)
CONTAINER_REGISTRY ?= quay.io
CONTAINER_REPO ?= <your-username>
CONTAINER_IMAGE ?= llm_proxy
CONTAINER_TAG ?= dev
FULL_TAG = $(CONTAINER_REGISTRY)/$(CONTAINER_REPO)/$(CONTAINER_IMAGE):$(CONTAINER_TAG)

.PHONY: archive
archive: $(ARCHIVE_NAME)

$(ARCHIVE_NAME): $(INCLUDE_FILE) $(INCLUDED_FILES)
	tar -czf $@ -C ../$(shell basename $(PWD)) -T $(abspath $(INCLUDE_FILE))

.PHONY: inspect
inspect: $(ARCHIVE_NAME)
	tar -tzf $<

.PHONY: build-image
build-image:
	podman build -t $(FULL_TAG) -f proxy/Containerfile proxy/

.PHONY: push-image
push-image:
	podman push $(FULL_TAG)

.PHONY: containertransfer
containertransfer:
	find proxy -type d -name __pycache__ -exec rm -rf {} +
	find proxy -type f -name '*.pyc' -delete
	ssh $(SSH_TARGET) 'mkdir -p $(REMOTE_WORKDIR)'
	scp -r proxy/* $(SSH_TARGET):$(REMOTE_WORKDIR)

.PHONY: containerupdate
containerupdate: containertransfer
	ssh $(SSH_TARGET) 'cd $(REMOTE_WORKDIR) && podman build -t $(FULL_TAG) -f Containerfile .'
	ssh $(SSH_TARGET) 'podman push $(FULL_TAG)'

.PHONY: tcetransfer
tcetransfer: $(ARCHIVE_NAME)
	ssh $(SSH_TARGET) 'mkdir -p $(REMOTE_WORKDIR)'
	scp $< $(SSH_TARGET):$(REMOTE_WORKDIR)

.PHONY: tcetemplate
tcetemplate: ../render_template.py
	ssh $(SSH_TARGET) 'mkdir -p $(REMOTE_WORKDIR)'
	scp $< $(SSH_TARGET):$(REMOTE_WORKDIR)

.PHONY: tceupdate
tceupdate: tcetransfer
	ssh $(SSH_TARGET) 'cat $(CATALOG_PASSWORD_FILE) | ai-services catalog login --server $(CATALOG_SERVER) --username $(CATALOG_USER) --insecure --password-stdin'
	ssh $(SSH_TARGET) "service_id=\$$(ai-services catalog bundle list | awk -v cid=$(CATALOG_ID) '\$$4==cid{print \$$1}'); ai-services catalog bundle update \$$service_id --file $(REMOTE_WORKDIR)/$(ARCHIVE_NAME)"

.PHONY: clean
clean:
	rm -f $(ARCHIVE_NAME)
