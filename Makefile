.PHONY: help
help: ## This help.
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n\nTargets:\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)
.DEFAULT_GOAL := help

IMAGE_NAME := django-filer-test
CONTAINER_NAME := django-filer-test-run
SHELL:=/bin/bash

## Build the test Docker image
test-build:
	docker build -f Dockerfile.test -t $(IMAGE_NAME) .

## Run unit tests in a Docker container
test:
	@if [ -z "$$(docker images -q $(IMAGE_NAME) 2>/dev/null)" ]; then \
		echo "Image not found, building..."; \
		$(MAKE) test-build; \
	fi
	docker run --rm --name $(CONTAINER_NAME) $(IMAGE_NAME)

## Run tests with verbose output and stop on first failure
test-verbose: test-build
	docker run --rm --name $(CONTAINER_NAME) $(IMAGE_NAME) \
		pytest -vx --ds=filer.test_settings --pyargs filer.tests

## Open a shell in the test container (useful for debugging)
test-shell: test-build
	docker run --rm -it --name $(CONTAINER_NAME) $(IMAGE_NAME) /bin/bash

## Remove the test Docker image
test-clean:
	-docker rmi $(IMAGE_NAME)

