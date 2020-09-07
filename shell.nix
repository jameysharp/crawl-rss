with import <nixpkgs> {};

mkShell {
  name = "crawl-rss";

  buildInputs = [
    (python3.withPackages (ps: [ ps.ipython ]))
    poetry
  ];

  # settings to make various things work in virtualenv:

  # set SOURCE_DATE_EPOCH to 1980 so that we can use python wheels
  # https://nixos.org/nixpkgs/manual/#python-setup.py-bdist_wheel-cannot-create-.whl
  SOURCE_DATE_EPOCH = 315532800;
}

