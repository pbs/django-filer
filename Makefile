.PHONY: help
help: ## This help.
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n\nTargets:\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)
.DEFAULT_GOAL := help

.PHONY: bump-pbs bump-prekind

IMAGE_NAME := django-filer-test
CONTAINER_NAME := django-filer-test-run
SHELL:=/bin/bash

test-build: ## Build the test Docker image
	docker build -f Dockerfile.test -t $(IMAGE_NAME) .

test: ## Run unit tests in a Docker container
	@if [ -z "$$(docker images -q $(IMAGE_NAME) 2>/dev/null)" ]; then \
		echo "Image not found, building..."; \
		$(MAKE) test-build; \
	fi
	docker run --rm --name $(CONTAINER_NAME) $(IMAGE_NAME)

test-verbose: test-build ## Run tests with verbose output and stop on first failure
	docker run --rm --name $(CONTAINER_NAME) $(IMAGE_NAME) \
		pytest -vx --ds=filer.test_settings --pyargs filer.tests

test-shell: test-build ## Open a shell in the test container (useful for debugging)
	docker run --rm -it --name $(CONTAINER_NAME) $(IMAGE_NAME) /bin/bash

test-clean: ## Remove the test Docker image
	-docker rmi $(IMAGE_NAME)


bump-pbs: ## Bump PBS number: 3.4.4+pbs.3 -> 3.4.4+pbs.4
	bump-my-version bump --allow-dirty pbs

bump-prekind: ## Bump prekind dev version: 3.4.4+pbs.3 -> 3.4.4+pbs.3.dev.g<sha>.YYYYMMDD
	@current=$$(grep "^__version__" filer/__init__.py | sed "s/^__version__ = '//;s/'.*//"); \
	if echo "$$current" | grep -q '\.dev\.'; then \
		echo "Nothing to bump: '$$current' is already a dev release from this commit. To create another dev release you must make at least one new commit first. To create a release bump run 'make bump-pbs'."; \
		exit 1; \
	fi; \
	sha="$${GITHUB_SHA:-$$(git rev-parse --short=8 HEAD)}"; \
	GITHUB_SHA="$${sha:0:8}" bump-my-version bump --allow-dirty prekind

