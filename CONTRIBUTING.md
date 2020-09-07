So you want to contribute improvements to this project? Awesome! I
really appreciate it.

Filing issues, improving documentation, suggesting usability fixes, etc
are all valuable contributions and I welcome whatever you've got!
However, I don't have specific requests for how I'd like you to approach
those; use your best judgement and it'll probably be great.

Instead, the following sections are specific to code contributions.

# Don't rebase

Unless you're super comfortable with git, please don't rebase your pull
requests. It's too easy to take code that worked and turn it into code
that's broken, while losing the history that shows how it should have
worked. If you do a merge and get it wrong, you can just try again, or
make a pull request and ask for help untangling things.

# Check tests and style

Please make sure that every commit passes `pytest --black --flakes`. I
enforce this on myself with a git pre-commit hook and I strongly
encourage you to do the same. My `.git/hooks/pre-commit` simply looks
like this:

```sh
#!/bin/sh
exec pytest --black --flakes
```

Make sure the hook is executable by running `chmod a+x
.git/hooks/pre-commit`.

# Include test cases with bug reports if you can

If you encounter a bug and you're prepared to write some code, the most
helpful thing you can do is write a test case which demonstrates the
bug, and open a pull request with it. If you can also fix the bug,
that's even better, but a test case is really ideal.

# Check test coverage

I'm not currently insisting on 100% test coverage but I will be more
excited about your contribution if it comes with tests that exercise
your new code well.

You can check test coverage at any time by running `pytest --cov`. A
summary will be printed at the end, and you can dive into the details by
opening the newly-generated `htmlcov/index.html` in your favorite web
browser.

If you aren't sure how to write tests for your changes, open an issue
and let's chat about it.
