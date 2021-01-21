{ pkgs ? import <nixpkgs> {} }:

let
  app = (import ./poetry.nix { inherit pkgs; }).mkPoetryApplication {
    projectDir = ./.;
  };
in pkgs.dockerTools.streamLayeredImage {
  name = "crawl-rss";
  contents = [
    app.dependencyEnv
    # handy for `docker enter`:
    pkgs.busybox
  ];
  config.Cmd = [ "/bin/sh" "-c" "/bin/uvicorn crawl_rss.server:app --port $PORT --host 0.0.0.0" ];
}
