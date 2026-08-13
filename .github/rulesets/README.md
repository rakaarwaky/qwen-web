# Rulesets — branch protection untuk `main`
Folder ini berisi definisi branch protection ruleset dalam format JSON untuk GitHub API.
Tujuannya: melarang push langsung ke `main` dan mewajibkan semua perubahan lewat PR.

> IMPORTANT: file JSON di sini TIDAK diterapkan otomatis. Ruleset disimpan di sisi GitHub
> (Settings -> Rules), jadi file ini hanya source-of-truth yang harus di-apply lewat script.

## Cara menerapkan (butuh role Admin + `gh` login)
```bash
bash scripts/apply-ruleset.sh                                   # versi dasar
bash scripts/apply-ruleset.sh .github/rulesets/ruleset-main-strict.json  # + wajib CI hijau
```
