{ pkgs ? import <nixpkgs> {} }:

let
  poetry2nix-src = pkgs.fetchFromGitHub {
    owner = "nix-community";
    repo = "poetry2nix";
    rev = "1.13.0";
    sha256 = "1lqzlkn1wxfdq4dvc7b3113b2xj5pjdhnw7qf4540dvh8c01k8dg";
  };

  poetry2nix = import poetry2nix-src {
    inherit pkgs;
    inherit (pkgs) poetry;
  };
in poetry2nix.overrideScope' (self: super: {
  defaultPoetryOverrides = super.defaultPoetryOverrides.extend (pyself: pysuper: {
    # from https://github.com/nix-community/poetry2nix/pull/217
    pytest = pysuper.pytest.overridePythonAttrs (
      old: {
        # Fixes https://github.com/pytest-dev/pytest/issues/7891
        postPatch = old.postPatch or "" + ''
          sed -i '/\[metadata\]/aversion = ${old.version}' setup.cfg
        '';
        doCheck = false;
      }
    );

    # black 20.8b1 doesn't have a wheel on pypi but somehow Poetry thinks it does
    black = pysuper.black.override { preferWheel = false; };
  });
})
