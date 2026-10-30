SHELL := /bin/bash -eu -o pipefail
export PATH := $(CURDIR)/.tools:$(PATH)
export RUSTC_WRAPPER := sccache
export FFMPEG_SRC_REQUIRE_SCCACHE := 1
export CARGO_INCREMENTAL := 0

.PHONY: setup check-version package build test clean
setup:
	python3 scripts/setup.py
	command -v sccache
	sccache --version
	cargo binstall --locked --no-confirm --disable-strategies compile --install-path .tools prek@0.5.5 cargo-audit@0.22.2 cargo-deny@0.20.2 cargo-machete@0.9.2
	prek prepare-hooks
check-version:
	python3 -c 'import pathlib,tomllib,subprocess; v=tomllib.loads(pathlib.Path("Cargo.toml").read_text())["package"]["version"]; assert v.split("-")[0] == pathlib.Path("ffmpeg/RELEASE").read_text().strip()+".0"; assert subprocess.check_output(["git","-C","ffmpeg","rev-parse","HEAD"]) == subprocess.check_output(["git","-C","ffmpeg","rev-parse","n8.0^{}"])'
package: check-version
	prek run -a
	cargo fmt --check
	cargo fmt --manifest-path testcrate/Cargo.toml --check
	python3 scripts/package.py
build: check-version
	cargo build --locked
test:
	python3 scripts/verify.py
clean:
	rm -rf target dist native testcrate/target
