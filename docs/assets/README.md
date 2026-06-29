# assets 素材文件夹 / Assets folder

把你的个人文件放在这个文件夹里。文件名要**完全一致**，主页会自动读取。

Put your personal files here. The file names must match **exactly** — the homepage loads them automatically.

| 文件名 / File name | 用途 / Purpose | 说明 / Notes |
|---|---|---|
| `profile.jpg`   | 职业照 / Portrait | 建议正方形，例如 600×600；命名必须是 `profile.jpg` |
| `resume-zh.pdf` | 中文简历 / Resume (CN) | 切到「中文」时下载这份 |
| `resume-en.pdf` | 英文简历 / Resume (EN) | 切到「EN」时下载这份 |

> 中英文简历已就位。若要更新简历，用同名文件覆盖即可。
> Both resumes are already in place — replace by overwriting the same file name.

## 怎么替换 / How to replace

- **网页操作（最简单）**：进入 GitHub 仓库的 `docs/assets/` 目录 → 点 **Add file → Upload files** → 把 `profile.jpg`、`resume.pdf` 拖进去 → Commit。
- **命令行**：把文件复制到本目录后 `git add`、`git commit`、`git push`。

> 如果你的照片是 `.png`，要么把它转成 `.jpg`，要么在 `../index.html` 的 `CONFIG.photo` 里把 `assets/profile.jpg` 改成 `assets/profile.png`。
> If your photo is a `.png`, either convert it to `.jpg`, or change `CONFIG.photo` in `../index.html`.
