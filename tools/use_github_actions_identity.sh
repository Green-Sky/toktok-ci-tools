#!/usr/bin/env bash

set -eux -o pipefail

# https://api.github.com/users/github-actions%5Bbot%5D
git config --global user.name "github-actions[bot]"
git config --global user.email "41898282+github-actions[bot]@users.noreply.github.com"

git remote add upstream "$GITHUB_SERVER_URL/$GITHUB_REPOSITORY"
git remote -v
