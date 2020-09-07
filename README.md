This is a work-in-progress RSS/Atom feed reader that supports finding
all old posts using either RFC5005 or a WordPress-specific hack. It is
essentially a reboot of my [reader-py][] project.

[reader-py]: https://github.com/jameysharp/reader-py

I've started writing several feed readers at this point, but this is the
first one where I'm trying to make it a solid piece of engineering
instead of just bashing together a prototype as quickly as possible. In
particular, this project has good code coverage in tests, static typing
everywhere, and consistent code style, all mechanically checked.

# Try it out

You need Python and [Poetry][] to run this. If you use the [Nix][]
package manager, you can run `nix-shell` in this directory to get both.

[Poetry]: https://python-poetry.org/
[Nix]: https://nixos.org/

With those prerequisites installed, run:

```sh
poetry install
```

That'll get you all the runtime and development dependencies for this
project.

After that you can run the tests with `pytest`. This project doesn't
have a good demo yet otherwise.
