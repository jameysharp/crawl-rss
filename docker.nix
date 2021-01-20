{ pkgs ? import <nixpkgs> {} }:

let
  app = (import ./poetry.nix { inherit pkgs; }).mkPoetryApplication {
    projectDir = ./.;
  };
in pkgs.dockerTools.streamLayeredImage {
  name = "crawl-rss";
  contents = [
    app.dependencyEnv
    # already in the closure and handy for `docker enter`:
    pkgs.bash
  ];
  config.Cmd = [ "/bin/sh" "-c" "/bin/uvicorn crawl_rss.server:app --port $PORT --host 0.0.0.0" ];
}
