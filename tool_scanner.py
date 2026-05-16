"""
Quét các CLI tool phổ biến đã cài đặt trên máy.

Dùng `shutil.which()` để tìm executable trong PATH. Mỗi tool có 1 template
command (vd `git status`, `docker ps`) — phù hợp làm "lệnh yêu thích" mẫu.

Hàm `detect_tools()` trả về list các tool tìm được trên máy hiện tại.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from typing import List


@dataclass
class ToolInfo:
    key: str           # tên executable (vd "git")
    category: str      # nhóm (vd "Version control")
    display_name: str  # tên hiển thị cho favorite (vd "Git status")
    command: str       # lệnh mẫu (vd "git status")
    shell: str = "any" # shell phù hợp (cmd | powershell | wsl | bash | any)
    path: str = ""     # full path sau khi detect


# Registry các CLI tool phổ biến + lệnh template
_TOOLS: list[ToolInfo] = [
    # ----- Version control -----
    ToolInfo("git",       "Version control", "Git status",            "git status"),
    ToolInfo("git",       "Version control", "Git log",               "git log --oneline -20"),
    ToolInfo("gh",        "Version control", "GitHub CLI: list repo", "gh repo list --limit 20"),
    ToolInfo("hg",        "Version control", "Mercurial status",      "hg status"),
    ToolInfo("svn",       "Version control", "SVN status",            "svn status"),

    # ----- Languages / runtimes -----
    ToolInfo("python",    "Languages",       "Python version",        "python --version"),
    ToolInfo("py",        "Languages",       "Python (py launcher)",  "py --version"),
    ToolInfo("node",      "Languages",       "Node version",          "node --version"),
    ToolInfo("deno",      "Languages",       "Deno version",          "deno --version"),
    ToolInfo("bun",       "Languages",       "Bun version",           "bun --version"),
    ToolInfo("go",        "Languages",       "Go version",            "go version"),
    ToolInfo("rustc",     "Languages",       "Rust version",          "rustc --version"),
    ToolInfo("java",      "Languages",       "Java version",          "java -version"),
    ToolInfo("javac",     "Languages",       "javac version",         "javac -version"),
    ToolInfo("dotnet",    "Languages",       ".NET info",             "dotnet --info"),
    ToolInfo("ruby",      "Languages",       "Ruby version",          "ruby --version"),
    ToolInfo("php",       "Languages",       "PHP version",           "php --version"),
    ToolInfo("perl",      "Languages",       "Perl version",          "perl --version"),
    ToolInfo("lua",       "Languages",       "Lua version",           "lua -v"),
    ToolInfo("Rscript",   "Languages",       "Rscript version",       "Rscript --version"),
    ToolInfo("julia",     "Languages",       "Julia version",         "julia --version"),

    # ----- Package managers -----
    ToolInfo("npm",       "Package managers", "npm global packages",  "npm list -g --depth=0"),
    ToolInfo("yarn",      "Package managers", "Yarn version",         "yarn --version"),
    ToolInfo("pnpm",      "Package managers", "pnpm version",         "pnpm --version"),
    ToolInfo("pip",       "Package managers", "pip list",             "pip list"),
    ToolInfo("pipx",      "Package managers", "pipx list",            "pipx list"),
    ToolInfo("uv",        "Package managers", "uv version",           "uv --version"),
    ToolInfo("poetry",    "Package managers", "Poetry version",       "poetry --version"),
    ToolInfo("cargo",     "Package managers", "Cargo version",        "cargo --version"),
    ToolInfo("composer",  "Package managers", "Composer version",     "composer --version"),
    ToolInfo("mvn",       "Package managers", "Maven version",        "mvn --version"),
    ToolInfo("gradle",    "Package managers", "Gradle version",       "gradle --version"),
    ToolInfo("choco",     "Package managers", "Choco list (local)",   "choco list --local-only"),
    ToolInfo("winget",    "Package managers", "Winget list",          "winget list"),
    ToolInfo("scoop",     "Package managers", "Scoop list",           "scoop list"),
    ToolInfo("brew",      "Package managers", "Brew list",            "brew list"),

    # ----- Containers / orchestration -----
    ToolInfo("docker",          "Containers", "Docker ps",            "docker ps"),
    ToolInfo("docker-compose",  "Containers", "Docker Compose ps",    "docker-compose ps"),
    ToolInfo("podman",          "Containers", "Podman ps",            "podman ps"),
    ToolInfo("kubectl",         "Containers", "kubectl get pods",     "kubectl get pods"),
    ToolInfo("helm",            "Containers", "Helm list releases",   "helm list"),
    ToolInfo("minikube",        "Containers", "Minikube status",      "minikube status"),
    ToolInfo("k3d",             "Containers", "k3d cluster list",     "k3d cluster list"),

    # ----- Cloud -----
    ToolInfo("aws",        "Cloud", "AWS: list S3 buckets",     "aws s3 ls"),
    ToolInfo("gcloud",     "Cloud", "gcloud projects",          "gcloud projects list"),
    ToolInfo("az",         "Cloud", "Azure account",            "az account show"),
    ToolInfo("terraform",  "Cloud", "Terraform version",        "terraform version"),
    ToolInfo("pulumi",     "Cloud", "Pulumi version",           "pulumi version"),
    ToolInfo("ansible",    "Cloud", "Ansible version",          "ansible --version"),

    # ----- Network / SSH -----
    ToolInfo("ssh",        "Network", "SSH version",            "ssh -V"),
    ToolInfo("scp",        "Network", "SCP help",               "scp"),
    ToolInfo("sftp",       "Network", "SFTP help",              "sftp"),
    ToolInfo("curl",       "Network", "curl version",           "curl --version"),
    ToolInfo("wget",       "Network", "wget version",           "wget --version"),
    ToolInfo("ping",       "Network", "Ping google",            "ping -n 4 google.com"),
    ToolInfo("nslookup",   "Network", "DNS lookup google",      "nslookup google.com"),
    ToolInfo("tracert",    "Network", "Trace route google",     "tracert google.com", "cmd"),
    ToolInfo("netstat",    "Network", "Active connections",     "netstat -ano"),
    ToolInfo("ipconfig",   "Network", "IP config (Windows)",    "ipconfig", "cmd"),
    ToolInfo("plink",      "Network", "PuTTY plink version",    "plink -V"),
    ToolInfo("openssl",    "Network", "OpenSSL version",        "openssl version"),

    # ----- Editors -----
    ToolInfo("code",       "Editors", "VS Code version",        "code --version"),
    ToolInfo("code-insiders", "Editors", "VS Code Insiders",    "code-insiders --version"),
    ToolInfo("subl",       "Editors", "Sublime Text version",   "subl --version"),
    ToolInfo("vim",        "Editors", "Vim version",            "vim --version"),
    ToolInfo("nvim",       "Editors", "Neovim version",         "nvim --version"),
    ToolInfo("nano",       "Editors", "nano version",           "nano --version"),

    # ----- Build / make -----
    ToolInfo("make",       "Build", "Make version",             "make --version"),
    ToolInfo("cmake",      "Build", "CMake version",            "cmake --version"),
    ToolInfo("ninja",      "Build", "Ninja version",            "ninja --version"),
    ToolInfo("bazel",      "Build", "Bazel version",            "bazel version"),

    # ----- Database / data -----
    ToolInfo("psql",       "Database", "PostgreSQL version",    "psql --version"),
    ToolInfo("mysql",      "Database", "MySQL version",         "mysql --version"),
    ToolInfo("mongosh",    "Database", "Mongo shell version",   "mongosh --version"),
    ToolInfo("sqlite3",    "Database", "SQLite version",        "sqlite3 --version"),
    ToolInfo("redis-cli",  "Database", "Redis ping",            "redis-cli ping"),

    # ----- Mobile / Android -----
    ToolInfo("adb",        "Mobile", "ADB devices",             "adb devices"),
    ToolInfo("fastboot",   "Mobile", "Fastboot version",        "fastboot --version"),

    # ----- Media -----
    ToolInfo("ffmpeg",     "Media", "ffmpeg version",           "ffmpeg -version"),
    ToolInfo("ffprobe",    "Media", "ffprobe version",          "ffprobe -version"),
    ToolInfo("convert",    "Media", "ImageMagick convert ver",  "convert --version"),
    ToolInfo("magick",     "Media", "ImageMagick version",      "magick -version"),
    ToolInfo("youtube-dl", "Media", "youtube-dl version",       "youtube-dl --version"),
    ToolInfo("yt-dlp",     "Media", "yt-dlp version",           "yt-dlp --version"),

    # ----- Windows-only utilities -----
    ToolInfo("tasklist",       "Windows utils", "Tasklist",         "tasklist", "cmd"),
    ToolInfo("systeminfo",     "Windows utils", "System info",      "systeminfo", "cmd"),
    ToolInfo("powercfg",       "Windows utils", "Power config",     "powercfg /list", "cmd"),
    ToolInfo("sfc",            "Windows utils", "SFC scan",         "sfc /scannow", "cmd"),

    # ----- Unix utilities -----
    ToolInfo("ls",         "Unix utils", "List files",              "ls -lah"),
    ToolInfo("pwd",        "Unix utils", "Current directory",       "pwd"),
    ToolInfo("ps",         "Unix utils", "Process list",            "ps aux"),
    ToolInfo("top",        "Unix utils", "Top processes",           "top -b -n 1"),
    ToolInfo("htop",       "Unix utils", "htop interactive",        "htop"),
    ToolInfo("free",       "Unix utils", "Memory info",             "free -h"),
    ToolInfo("df",         "Unix utils", "Disk usage",              "df -h"),
    ToolInfo("du",         "Unix utils", "Directory size",          "du -sh ."),
    ToolInfo("uname",      "Unix utils", "Kernel info",             "uname -a"),
    ToolInfo("uptime",     "Unix utils", "System uptime",           "uptime"),
    ToolInfo("whoami",     "Unix utils", "Current user",            "whoami"),
    ToolInfo("id",         "Unix utils", "User/group IDs",          "id"),
    ToolInfo("env",        "Unix utils", "Environment variables",   "env"),
    ToolInfo("lsb_release","Unix utils", "Distro info (LSB)",       "lsb_release -a"),

    # ----- Linux package managers -----
    ToolInfo("apt",        "Linux packages", "APT installed",       "apt list --installed"),
    ToolInfo("apt-get",    "Linux packages", "apt-get update",      "sudo apt-get update"),
    ToolInfo("dpkg",       "Linux packages", "dpkg list",           "dpkg -l"),
    ToolInfo("yum",        "Linux packages", "yum list installed",  "yum list installed"),
    ToolInfo("dnf",        "Linux packages", "dnf list installed",  "dnf list installed"),
    ToolInfo("rpm",        "Linux packages", "rpm query all",       "rpm -qa"),
    ToolInfo("pacman",     "Linux packages", "Pacman query",        "pacman -Q"),
    ToolInfo("zypper",     "Linux packages", "zypper search inst",  "zypper search --installed-only"),
    ToolInfo("snap",       "Linux packages", "Snap list",           "snap list"),
    ToolInfo("flatpak",    "Linux packages", "Flatpak list",        "flatpak list"),
    ToolInfo("apk",        "Linux packages", "apk info",            "apk info"),

    # ----- systemd / services -----
    ToolInfo("systemctl",  "Systemd", "List units",                 "systemctl list-units"),
    ToolInfo("journalctl", "Systemd", "Recent log",                 "journalctl -n 50"),
    ToolInfo("service",    "Systemd", "Service status",             "service --status-all"),

    # ----- macOS -----
    ToolInfo("sw_vers",    "macOS", "macOS version",                "sw_vers"),
    ToolInfo("launchctl",  "macOS", "List launch agents",           "launchctl list"),
    ToolInfo("diskutil",   "macOS", "Disk utility list",            "diskutil list"),
    ToolInfo("defaults",   "macOS", "Read defaults",                "defaults read"),
    ToolInfo("pmset",      "macOS", "Power management",             "pmset -g"),

    # ----- Misc -----
    ToolInfo("jq",         "Misc", "jq version",                "jq --version"),
    ToolInfo("rg",         "Misc", "ripgrep version",           "rg --version"),
    ToolInfo("fd",         "Misc", "fd version",                "fd --version"),
    ToolInfo("bat",        "Misc", "bat version",               "bat --version"),
    ToolInfo("tar",        "Misc", "tar version",               "tar --version"),
    ToolInfo("zip",        "Misc", "zip version",               "zip --version"),
    ToolInfo("unzip",      "Misc", "unzip version",             "unzip -v"),
    ToolInfo("7z",         "Misc", "7-Zip version",             "7z --help"),
]


def detect_tools() -> List[ToolInfo]:
    """
    Quét PATH tìm các CLI tool đã cài. Trả về list ToolInfo với .path
    là full path tới executable.

    Có thể trả về cùng `key` nhiều lần nếu registry có nhiều entries cho cùng
    1 tool (vd git status, git log) — đó là tính năng, mỗi entry là 1 lệnh mẫu.
    """
    found: List[ToolInfo] = []
    cache: dict[str, str | None] = {}  # cache shutil.which() cho cùng key
    for tool in _TOOLS:
        if tool.key not in cache:
            cache[tool.key] = shutil.which(tool.key)
        path = cache[tool.key]
        if path:
            # tạo bản copy với path đã điền
            found.append(
                ToolInfo(
                    key=tool.key,
                    category=tool.category,
                    display_name=tool.display_name,
                    command=tool.command,
                    shell=tool.shell,
                    path=path,
                )
            )
    # sort: theo category rồi theo display_name
    found.sort(key=lambda t: (t.category, t.display_name))
    return found
