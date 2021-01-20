{ pkgs ? import <nixpkgs> {} }:

let
  poetry2nix = import ./poetry.nix { inherit pkgs; };
  app = poetry2nix.mkPoetryEnv {
    projectDir = ./.;
    editablePackageSources.crawl_rss = ./.;

    overrides = poetry2nix.overrides.withDefaults (self: super: {
      # starlette source doesn't include py.typed but its wheel does
      starlette = super.starlette.override { preferWheel = true; };
    });
  };
in pkgs.mkShell { buildInputs = [ app pkgs.poetry ]; }
