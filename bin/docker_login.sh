#!/usr/bin/env bash

echo "${GITHUB_TOKEN}" | docker login https://docker.pkg.github.com -u cloudwebmanage --password-stdin
