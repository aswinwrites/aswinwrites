# Setup

1. Create a new **public** repo named exactly `aswinwrites`.
2. Push README.md, .github/workflows/knight.yml, scripts/generate_knight.py to `main`.
3. Settings → Actions → General → Workflow permissions → Read and write permissions → Save.
4. Actions tab → generate-knight-animation → Run workflow (creates the `output` branch with the SVGs).
5. If the Action fails on auth: create a classic PAT with `read:user` scope, save as secret `KNIGHT_PAT`, and swap `secrets.GITHUB_TOKEN` for `secrets.KNIGHT_PAT` in knight.yml.
