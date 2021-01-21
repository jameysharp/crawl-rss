{ pkgs ? import <nixpkgs> {} }:

let
  app = (import ./poetry.nix { inherit pkgs; }).mkPoetryApplication {
    projectDir = ./.;
  };
in pkgs.dockerTools.streamLayeredImage {
  name = "crawl-rss";
  contents = [
    (app.dependencyEnv.override {
      postBuild = ''
        # glibc doesn't have defaults for NSS any more I guess?
        mkdir -p $out/etc
        echo "hosts: files dns" > $out/etc/nsswitch.conf

        # Symlink the app itself into a common location. Since the resulting
        # environment is part of the "contents" attribute, this symlink will be
        # available at the root of the generated Docker image.
        ln -s ${app}/${app.python.sitePackages} $out/app
      '';
    })

    # handy for `docker enter`:
    pkgs.busybox
  ];
  config.Cmd = [ "/bin/sh" "-c" "/bin/uvicorn crawl_rss.server:app --port $PORT --host 0.0.0.0" ];
}
