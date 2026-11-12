#!/bin/sh
# Rebuild share-check.wasm byte for byte and compare it with dist/.
#
# The compiler embeds the path of the crate cache in panic messages, so the
# build maps whatever CARGO_HOME you use onto the path the original build
# used. With the pinned toolchain (rust-toolchain.toml) and Cargo.lock, the
# result is identical. Needs rustup and a host C linker (cc) for build scripts.
set -e
cd "$(dirname "$0")"
home="${CARGO_HOME:-$HOME/.cargo}"
RUSTFLAGS="--remap-path-prefix=$home=/home/god/.cargo" \
  cargo build --locked --target wasm32-wasip2 --release
built=$(sha256sum target/wasm32-wasip2/release/share-check.wasm | cut -d' ' -f1)
committed=$(cut -d' ' -f1 dist/share-check.wasm.sha256)
echo "rebuilt   $built"
echo "committed $committed"
[ "$built" = "$committed" ] && echo "IDENTICAL" || { echo "DIFFERENT"; exit 1; }
