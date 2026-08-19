aespinel@Augustos-Mac-Studio-2 hephaistus % npm install

added 1 package, and audited 221 packages in 38s

65 packages are looking for funding
  run `npm fund` for details

8 vulnerabilities (1 moderate, 7 high)

To address issues that do not require attention, run:
  npm audit fix

To address all issues (including breaking changes), run:
  npm audit fix --force

Run `npm audit` for details.
aespinel@Augustos-Mac-Studio-2 hephaistus % npm audit
# npm audit report

minimatch  9.0.0 - 9.0.6
Severity: high
minimatch has a ReDoS via repeated wildcards with non-matching literal in pattern - https://github.com/advisories/GHSA-3ppc-4f35-3m26
minimatch has ReDoS: matchOne() combinatorial backtracking via multiple non-adjacent GLOBSTAR segments - https://github.com/advisories/GHSA-7r86-cg39-jmmj
minimatch ReDoS: nested *() extglobs generate catastrophically backtracking regular expressions - https://github.com/advisories/GHSA-23c5-xmqv-rm74
fix available via `npm audit fix`
node_modules/minimatch
  @typescript-eslint/typescript-estree  6.16.0 - 7.5.0
  Depends on vulnerable versions of minimatch
  node_modules/@typescript-eslint/typescript-estree
    @typescript-eslint/parser  6.16.0 - 7.5.0
    Depends on vulnerable versions of @typescript-eslint/typescript-estree
    node_modules/@typescript-eslint/parser
    @typescript-eslint/type-utils  6.16.0 - 7.5.0
    Depends on vulnerable versions of @typescript-eslint/typescript-estree
    Depends on vulnerable versions of @typescript-eslint/utils
    node_modules/@typescript-eslint/type-utils
    @typescript-eslint/utils  6.16.0 - 7.5.0
    Depends on vulnerable versions of @typescript-eslint/typescript-estree
    node_modules/@typescript-eslint/utils
      @typescript-eslint/eslint-plugin  6.16.0 - 7.5.0
      Depends on vulnerable versions of @typescript-eslint/type-utils
      Depends on vulnerable versions of @typescript-eslint/utils
      node_modules/@typescript-eslint/eslint-plugin

serialize-javascript  <=7.0.4
Severity: high
Serialize JavaScript is Vulnerable to RCE via RegExp.flags and Date.prototype.toISOString() - https://github.com/advisories/GHSA-5c6j-r48x-rmvq
Serialize JavaScript has CPU Exhaustion Denial of Service via crafted array-like objects - https://github.com/advisories/GHSA-qj8w-gfj5-8c6v
fix available via `npm audit fix --force`
Will install mocha@8.1.3, which is a breaking change
node_modules/serialize-javascript
  mocha  8.2.0 - 12.0.0-beta-2
  Depends on vulnerable versions of serialize-javascript
  node_modules/mocha

8 vulnerabilities (1 moderate, 7 high)

To address issues that do not require attention, run:
  npm audit fix

To address all issues (including breaking changes), run:
  npm audit fix --force
aespinel@Augustos-Mac-Studio-2 hephaistus % npm run compile
npm error Missing script: "compile"
npm error
npm error To see a list of scripts, run:
npm error   npm run
npm error A complete log of this run can be found in: /Users/aespinel/.npm/_logs/2026-07-18T07_51_44_664Z-debug-0.log
aespinel@Augustos-Mac-Studio-2 hephaistus % 
