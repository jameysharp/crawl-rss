with import <nixpkgs> {};

mkShell {
  name = "crawl-rss";

  buildInputs = [
    (python3.withPackages (ps: [ ps.ipython ]))

    (poetry.overrideAttrs (oldAttrs: {
      propagatedBuildInputs = oldAttrs.propagatedBuildInputs ++ [ python3.pkgs.setuptools ];
      postPatch = oldAttrs.postPatch + ''
        substituteInPlace setup.py --replace 'pyrsistent>=0.14.2,<0.15.0' 'pyrsistent>=0.14.2,<0.16.0'
      '';
    }))

    mypy
    (with python3.pkgs; toPythonApplication black)
    (with python3.pkgs; toPythonApplication flake8)
  ];

  # settings to make various things work in virtualenv:

  # set SOURCE_DATE_EPOCH to 1980 so that we can use python wheels
  # https://nixos.org/nixpkgs/manual/#python-setup.py-bdist_wheel-cannot-create-.whl
  SOURCE_DATE_EPOCH = 315532800;
}

