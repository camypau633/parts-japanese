# CatCar access-policy discovery

Date: 2026-11-02

## Checks performed

A limited policy-discovery request was made from GitHub Actions:

- `https://www.catcar.info/robots.txt`
- `https://www.catcar.info/`

Both returned HTTP 200.

## robots.txt

The current response was:

```
User-agent: *
Crawl-delay: 10
Host: https://www.catcar.info
```

There are no `Disallow` or `Allow` rules in the returned file. The site publishes a crawl delay of 10 seconds for all user agents. Treat this as an operational limit and do not send requests faster than this interval during any future permitted test.

## Published usage terms

The homepage was inspected for links whose text or URL indicates terms, rules, privacy, license, agreement, or user policy. No such links were found.

This does **not** establish that automated extraction or reuse is permitted. A robots.txt file is not a license, and the absence of a linked policy is not consent.

## Decision

- Keep mass collection disabled.
- Do not bypass access controls, rate limits, or blocks.
- Before any bulk collection or redistribution, obtain explicit clarification/permission from the site operator or locate applicable contractual terms.
- If a later bounded technical test is authorized, respect the published 10-second crawl delay and stop on errors, blocks, or unusual response behavior.

## Evidence limits

This was a narrow check of the current robots.txt and homepage links. It is not legal advice and does not rule out terms published elsewhere, contractual restrictions, copyright/database rights, or restrictions imposed by third-party image/data owners.
