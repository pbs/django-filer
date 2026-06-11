.PHONY: help
help: ## This help.
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n\nTargets:\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)
.DEFAULT_GOAL := help

.PHONY: bump-pbs bump-prekind build publish-nexus publish-nexus-dry-run

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
	sha="$${GITHUB_SHA:-$$(git rev-parse --short=8 HEAD)}"; \
	sha8="$${sha:0:8}"; \
	if echo "$$current" | grep -q '\.dev\.'; then \
		current_sha=$$(echo "$$current" | sed -nE "s/.*\.dev\.g([0-9a-f]{7,40})\.[0-9]{8}/\1/p"); \
		current_sha8="$${current_sha:0:8}"; \
		if [ "$$current_sha8" = "$$sha8" ]; then \
			echo "Nothing to bump: '$$current' already targets commit '$$sha8'. Create a new commit first or run 'make bump-pbs'."; \
			exit 1; \
		fi; \
		base=$$(echo "$$current" | sed -E "s/\.dev\.g[0-9a-f]+\.[0-9]{8}$$//"); \
		new_version="$$base.dev.g$$sha8.$$(date +%Y%m%d)"; \
	else \
		base="$$current"; \
		new_version="$$base.dev.g$$sha8.$$(date +%Y%m%d)"; \
	fi; \
	echo "Bumping: $$current -> $$new_version"; \
	sed -i.bak "s/__version__ = '$$current'/__version__ = '$$new_version'/" filer/__init__.py && rm -f filer/__init__.py.bak; \
	sed -i.bak -E "s/^current_version = \"[^\"]+\"/current_version = \"$$new_version\"/" .bumpversion.toml && rm -f .bumpversion.toml.bak


build: ## Build distribution packages (sdist and wheel)
	rm -rf dist/ build/ *.egg-info
	python3 -m pip install --upgrade --break-system-packages build
	python3 -m build

publish-nexus: build ## Publish to Nexus using ~/.pypirc config
	python3 -m pip install --upgrade --break-system-packages twine
	python3 -m twine upload -r nexus dist/*

publish-nexus-dry-run: build ## Validate packages ready for Nexus (without uploading)
	python3 -m pip install --upgrade --break-system-packages twine
	python3 -m twine check dist/*

