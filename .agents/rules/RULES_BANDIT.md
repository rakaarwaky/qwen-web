# Bandit Security Rules

See [README.md](../README.md) for Python adapter usage and [RULES_RUFF.md](RULES_RUFF.md) for related Python linting.

Bandit is a security linter for Python code, available at https://bandit.readthedocs.io/. It detects common security issues by walking the Python AST.

## B100–B199: Assert & Hash

| Code | Name                          | Description                                                                                                                                |
| ---- | ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| B101 | assert_used                   | Use of `assert` detected. `assert` statements are stripped in optimized bytecode (`python -O`) and should not be used for security checks. |
| B102 | exec_used                     | Use of `exec` detected. `exec` executes arbitrary Python code and is a high-risk operation.                                                |
| B103 | set_bad_file_permissions      | Setting file permissions with `os.chmod` using overly permissive values.                                                                   |
| B104 | hardcoded_bind_all_interfaces | Binding to `0.0.0.0` exposes the service to all network interfaces.                                                                        |
| B105 | hardcoded_password_string     | Hardcoded password or secret detected in source code.                                                                                      |
| B106 | hardcoded_password_funcarg    | Function argument with password-like name and default value.                                                                               |
| B107 | hardcoded_password_default    | Hardcoded password as a function default argument.                                                                                         |
| B108 | hardcoded_tmp_directory       | Use of hardcoded temp directory path (e.g., `/tmp/`) instead of `tempfile` module.                                                         |
| B110 | try_except_pass               | `except: pass` silently swallows exceptions. At minimum log the exception.                                                                 |
| B112 | try_except_continue           | `except: continue` silently swallows exceptions in a loop.                                                                                 |

## B200–B299: HTTP & Network

| Code | Name                             | Description                                                                                       |
| ---- | -------------------------------- | ------------------------------------------------------------------------------------------------- |
| B201 | flask_debug_true                 | Flask app running with `debug=True`, which enables the debugger in production.                    |
| B202 | tarfile_unsafe_member_extraction | Unsafe extraction of a tarfile member that could escape the target directory.                     |
| B203 | yaml_load                        | `yaml.load()` without `Loader` parameter allows arbitrary code execution. Use `yaml.safe_load()`. |
| B204 | xml_bad_cElementTree             | Use of `xml.etree.cElementTree` which is vulnerable to XML entity expansion.                      |
| B205 | xml_bad_ElementTree              | Use of `xml.etree.ElementTree` without proper parser configuration.                               |

## B300–B399: Cryptography

| Code | Name            | Description                                                                              |
| ---- | --------------- | ---------------------------------------------------------------------------------------- |
| B301 | pickle_load     | `pickle.load()` and similar functions can execute arbitrary code during deserialization. |
| B302 | marshal_load    | `marshal.load()` deserializes arbitrary objects unsafely.                                |
| B303 | md5_insecure    | Use of MD5 hash algorithm which is cryptographically broken.                             |
| B304 | cipher_no_mode  | Cipher is used without specifying a secure mode of operation.                            |
| B305 | cipher_mode_ecb | ECB mode cipher operation is deterministic and leaks data patterns. Use CBC or GCM.      |
| B306 | mktemp_qsd      | Use of `tempfile.mktemp()` which creates temporary files insecurely.                     |
| B307 | eval            | Use of `eval()` executes arbitrary Python expressions.                                   |
| B308 | mark_safe       | Use of `django.utils.safestring.mark_safe` on user input without escaping.               |
| B309 | httpsconnection | Use of `HTTPSConnection` without proper certificate validation.                          |
| B310 | urllib_urlopen  | Use of `urllib.urlopen()` without proper certificate validation.                         |

## B400–B499: XML & Input

| Code | Name              | Description                                                                 |
| ---- | ----------------- | --------------------------------------------------------------------------- |
| B401 | import_xml_etree  | Import of `xml.etree.ElementTree` which is vulnerable to XXE attacks.       |
| B402 | import_xml_sax    | Import of `xml.sax` parser which is vulnerable to XXE and entity expansion. |
| B403 | import_xml_dom    | Import of `xml.dom` which is vulnerable to XML bombs (Billion Laughs).      |
| B404 | import_subprocess | Import of `subprocess` module which can be used to execute system commands. |

## B500–B599: SQL & Database

| Code | Name                         | Description                                                             |
| ---- | ---------------------------- | ----------------------------------------------------------------------- |
| B501 | request_no_cert_validation   | HTTP request with certificate validation disabled (`verify=False`).     |
| B502 | ssl_no_version               | SSL context created without specifying a minimum TLS version.           |
| B503 | ssl_bad_version              | SSL context using an insecure protocol version (SSLv2, SSLv3, TLSv1.0). |
| B504 | ssl_with_bad_defaults        | SSL context created with potentially insecure default settings.         |
| B505 | weak_cryptographic_key       | Use of weak cryptographic key sizes (e.g., RSA < 2048 bits).            |
| B506 | yaml_load_dangerous          | Use of `yaml.load()` with unsafe deserialization.                       |
| B507 | ssh_no_host_key_verification | SSH connection without host key verification.                           |

## B600–B699: Shell & Command

| Code | Name                                      | Description                                                              |
| ---- | ----------------------------------------- | ------------------------------------------------------------------------ |
| B601 | paramiko_calls                            | Paramiko SSH calls without proper host key checking.                     |
| B602 | subprocess_popen_with_shell_equals_true   | `subprocess.Popen(..., shell=True)` enables shell injection.             |
| B603 | subprocess_without_shell_equals_true      | Use of `subprocess` without shell but validate arguments.                |
| B604 | any_other_function_with_shell_equals_true | Any function called with `shell=True` is dangerous.                      |
| B605 | start_process_with_partial_path           | Starting a process using a partial/relative path enables path injection. |
| B606 | start_process_with_no_shell               | Starting processes without shell but check argument injection.           |
| B607 | start_process_with_partial_path           | Starting process with relative path (duplicate of B605 variant).         |
| B608 | hardcoded_sql_expressions                 | Hardcoded SQL expressions detected — risk of SQL injection.              |
| B609 | linux_commands_wildcard_injection         | Linux commands using shell wildcards can inject arguments.               |

## B700–B799: General & Other

| Code | Name                    | Description                                                                |
| ---- | ----------------------- | -------------------------------------------------------------------------- |
| B701 | jinja2_autoescape_false | Jinja2 template with `autoescape=False` enables XSS in rendered templates. |
| B702 | use_of_mako_templates   | Mako templates evaluate arbitrary Python code in templates.                |
| B703 | django_mark_safe        | Django `mark_safe()` applied to user input creates XSS vulnerabilities.    |
