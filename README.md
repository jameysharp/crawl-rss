This is a work-in-progress RSS/Atom feed reader that supports finding
all old posts using [RFC5005][]. It is essentially a reboot of my
[reader-py][] project.

[RFC5005]: https://tools.ietf.org/html/rfc5005
[reader-py]: https://github.com/jameysharp/reader-py

I've started writing several feed readers at this point, but this is the
first one where I'm trying to make it a solid piece of engineering
instead of just bashing together a prototype as quickly as possible. In
particular, this project has good code coverage in tests, static typing
everywhere, and consistent code style, all mechanically checked.


## Adaptors for non-RFC5005 feeds

At this time there are very few RFC5005-compliant RSS or Atom feeds in
the wild. As a transition measure, this feed reader supports using
special-purpose proxies to synthesize a compliant feed from a
non-compliant one by taking advantage of special knowledge about
specific sites or publishing platforms.

I'm currently aware of adaptors for these platforms:

- [WordPress](https://github.com/jameysharp/wp-5005-proxy)


## External caching

This application relies on an external HTTP caching proxy, such as
[Squid][], to store full feed contents. You can run it without a cache
but it will be slow and tend to issue a lot of duplicate requests for
feed documents.

[Squid]: http://www.squid-cache.org/

Feed readers generally save posts in a local database of some form,
because in the absence of an RFC5005 archive, posts can disappear from a
feed at any time.

This feed reader instead assumes that if a post isn't in an RFC5005
archive, its author doesn't think it was important. As a result, we
should always be able to retrieve a post from the origin server if
somebody wants to read it after it dropped out of our local cache.

The server administrator can configure the caching proxy to use a
limited amount of disk space for saving feed archives, or scale up to a
global network of caches if desired. This application doesn't require
any configuration for those scenarios; it just sends standard HTTP
requests and lets the proxy sort it out.


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
project, installed into an isolated Python environment.

You can use `poetry run <command>` to run a command in that environment,
such as `poetry run pytest --cov` (to run the test suite and check test
coverage). Or you can run `poetry shell` which drops you into a shell
prompt that has access to the right Python environment.

Now you can run the web server for this project.

```sh
DEBUG=1 uvicorn --reload crawl_rss.server:app
```

I strongly recommend configuring a caching HTTP proxy. If you're running
[Squid][] on localhost, for example, set
`HTTP_PROXY=http://localhost:3128`.
