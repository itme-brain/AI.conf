set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

default: help

help:
  @just --list

validate:
  nix run .#validate

build:
  nix run .#build

check:
  nix run .#check

install:
  nix run .#install

clean:
  rm -rf settings.json claude codex opencode/agents opencode/AGENTS.md opencode/opencode.json
