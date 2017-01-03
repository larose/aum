SHELL = /bin/bash
BUILD_DIR = build
CACHE_DIR = cache
GIT_REMOTE_DEPLOY = dokku@d1.mathieularose.com:aum
USE_CACHE ?= n


INIT_GIT_REPO := cd $(BUILD_DIR) && git init && git add . && git commit --allow-empty-message -m ""
PUSH_GIT_REPO := cd $(BUILD_DIR) && git push -f $(GIT_REMOTE_DEPLOY) master

.PHONY: add-key
add-key:
	mkdir -p ~/.ssh
	echo '|1|/Y3D71mvgFfOFAmAJZrMp+cXgk8=|XaiZPABJ5JGR+kp+/OPrE9i87JU= ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAAABBBNqAqMgx2OxeQ69xnBKq2Q3D54rhVItx/Ix42o2VN0FG1sBOQJoID6+HT5Rujgu2auC2jWsgUmPJCHIk9Q97GyE=' > ~/.ssh/known_hosts
	echo "$$SSH_PRIVATE_KEY" |  tr '#' '\n' > ~/.ssh/id_rsa
	echo "$$SSH_PUBLIC_KEY" | tr '#' '\n' > ~/.ssh/id_rsa.pub
	chmod 600 ~/.ssh/id_rsa

.PHONY: env
env:
	virtualenv --no-site-packages env -p python3
	source env/bin/activate && pip install -r requirements.txt

.PHONY: clean
clean:
	rm -rf $(BUILD_DIR)
	mkdir -p $(BUILD_DIR)
	touch $(BUILD_DIR)/.static
	rm -rf $(CACHE_DIR)

.PHONY: deploy
deploy: clean generate
	$(INIT_GIT_REPO)
	$(PUSH_GIT_REPO)

.PHONY: deploy-from-updater
deploy-from-updater: clean generate add-key
	$(INIT_GIT_REPO)
	$(PUSH_GIT_REPO)

.PHONY: generate
generate:
	mkdir -p $(BUILD_DIR)
	rm -rf $(BUILD_DIR)/*
	USE_CACHE=$(USE_CACHE) python3 generate.py
	cp style.css $(BUILD_DIR)
	cp app-nginx.conf.sigil $(BUILD_DIR)
	touch $(BUILD_DIR)/.static

.PHONY: start
start:
	cd $(BUILD_DIR) && python3 -m http.server
