"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = activate;
exports.deactivate = deactivate;
const licensing_1 = require("@toolworks/licensing");
const vscode = __importStar(require("vscode"));
const flakiness_1 = require("./analysis/flakiness");
const git_1 = require("./ingest/git");
const junit_1 = require("./ingest/junit");
const history_1 = require("./store/history");
// TODO: 마켓플레이스 게시 전에 실제 Gumroad 제품 ID로 교체한다. APPROVALS.md 승인 #2 참조.
const GUMROAD_PRODUCT_ID = "REPLACE_ME";
const BUY_URL = "https://gumroad.com";
const HISTORY_FILE = "history.json";
async function activate(context) {
    const gate = new licensing_1.LicenseGate({ productId: GUMROAD_PRODUCT_ID }, (0, licensing_1.memento)(context.globalState));
    const store = new history_1.HistoryStore(new WorkspaceIO(context), maxRuns());
    const provider = new VerdictTree(store, gate);
    context.subscriptions.push(vscode.window.registerTreeDataProvider("flakyRadar.verdicts", provider), vscode.commands.registerCommand("flakyRadar.refresh", () => provider.refresh()), vscode.commands.registerCommand("flakyRadar.enterLicense", () => enterLicense(gate, provider)), vscode.commands.registerCommand("flakyRadar.buy", () => vscode.env.openExternal(vscode.Uri.parse(BUY_URL))), vscode.commands.registerCommand("flakyRadar.showStatus", () => showStatus(gate)), vscode.commands.registerCommand("flakyRadar.clearHistory", async () => {
        const yes = "지우기";
        const answer = await vscode.window.showWarningMessage("이 워크스페이스의 테스트 실행 이력을 모두 지웁니다. 되돌릴 수 없습니다.", { modal: true }, yes);
        if (answer === yes) {
            await store.clear();
            provider.refresh();
        }
    }), ...watchResults(context, store, provider));
    provider.refresh();
}
function deactivate() {
    // 파일 감시자는 subscriptions로 정리된다.
}
// ── 결과 파일 감시 ────────────────────────────────────────
function watchResults(context, store, provider) {
    const patterns = vscode.workspace
        .getConfiguration("flakyRadar")
        .get("resultPatterns", []);
    return patterns.map((pattern) => {
        const watcher = vscode.workspace.createFileSystemWatcher(pattern);
        const onChange = (uri) => void ingest(uri, store, provider);
        watcher.onDidCreate(onChange, undefined, context.subscriptions);
        watcher.onDidChange(onChange, undefined, context.subscriptions);
        return watcher;
    });
}
async function ingest(uri, store, provider) {
    let xml;
    try {
        xml = Buffer.from(await vscode.workspace.fs.readFile(uri)).toString("utf8");
    }
    catch {
        return; // 쓰는 도중에 읽었을 수 있다. 다음 이벤트에서 다시 잡힌다.
    }
    const commit = await currentCommit(uri);
    try {
        // runId를 경로+수정시각으로 잡아 같은 저장이 두 번 집계되지 않게 한다.
        // 파일 감시자는 저장 한 번에 이벤트를 여러 번 쏜다.
        const stat = await vscode.workspace.fs.stat(uri);
        const run = (0, junit_1.parseJUnit)(xml, {
            runId: `${uri.fsPath}@${stat.mtime}`,
            at: stat.mtime,
            commit,
        });
        if (run.results.length === 0)
            return;
        await store.append(run);
        provider.refresh();
    }
    catch (error) {
        if (error instanceof junit_1.JUnitParseError)
            return; // JUnit XML이 아닌 파일. 조용히 넘어간다.
        throw error;
    }
}
async function currentCommit(resultUri) {
    const folder = vscode.workspace.getWorkspaceFolder(resultUri);
    if (!folder)
        return undefined;
    const reader = {
        read: async (relativePath) => {
            try {
                const uri = vscode.Uri.joinPath(folder.uri, ".git", relativePath);
                return Buffer.from(await vscode.workspace.fs.readFile(uri)).toString("utf8");
            }
            catch {
                return undefined;
            }
        },
    };
    return await (0, git_1.resolveCommit)(reader);
}
// ── 저장소 ────────────────────────────────────────────────
/** 이력은 워크스페이스별 데이터라 globalState가 아니라 storageUri에 둔다. */
class WorkspaceIO {
    context;
    constructor(context) {
        this.context = context;
    }
    uri() {
        return this.context.storageUri
            ? vscode.Uri.joinPath(this.context.storageUri, HISTORY_FILE)
            : undefined;
    }
    async read() {
        const uri = this.uri();
        if (!uri)
            return undefined;
        try {
            return Buffer.from(await vscode.workspace.fs.readFile(uri)).toString("utf8");
        }
        catch {
            return undefined;
        }
    }
    async write(contents) {
        const uri = this.uri();
        if (!uri || !this.context.storageUri)
            return;
        await vscode.workspace.fs.createDirectory(this.context.storageUri);
        await vscode.workspace.fs.writeFile(uri, Buffer.from(contents, "utf8"));
    }
}
class VerdictTree {
    store;
    gate;
    emitter = new vscode.EventEmitter();
    onDidChangeTreeData = this.emitter.event;
    constructor(store, gate) {
        this.store = store;
        this.gate = gate;
    }
    refresh() {
        this.emitter.fire();
    }
    async getChildren(node) {
        if (node)
            return [];
        const entitlement = await this.gate.check();
        if (entitlement.status === "expired" || entitlement.status === "revoked") {
            return [
                { kind: "message", label: "체험이 끝났습니다 — 계속 쓰려면 구매해 주세요", command: "flakyRadar.buy" },
                { kind: "message", label: "이미 구매하셨다면: 라이선스 키 입력", command: "flakyRadar.enterLicense" },
            ];
        }
        const history = await this.store.load();
        if (history.runs.length === 0) {
            return [
                {
                    kind: "message",
                    label: "아직 테스트 결과가 없습니다. JUnit XML을 내보내도록 러너를 설정해 주세요",
                },
            ];
        }
        const verdicts = (0, flakiness_1.analyze)(history, { minRuns: minRuns() }).filter((v) => v.flakiness > 0);
        if (verdicts.length === 0) {
            return [{ kind: "message", label: `불안정한 테스트가 없습니다 (실행 ${history.runs.length}회 분석)` }];
        }
        return verdicts.map((verdict) => ({ kind: "verdict", verdict }));
    }
    getTreeItem(node) {
        if (node.kind === "message") {
            const item = new vscode.TreeItem(node.label, vscode.TreeItemCollapsibleState.None);
            if (node.command)
                item.command = { command: node.command, title: node.label };
            return item;
        }
        const { verdict } = node;
        const percent = Math.round(verdict.flakiness * 100);
        const item = new vscode.TreeItem(`${percent}%  ${verdict.name}`, vscode.TreeItemCollapsibleState.None);
        item.description = `${verdict.suite} · ${verdict.failures}/${verdict.totalRuns} 실패`;
        item.iconPath = new vscode.ThemeIcon(verdict.flakiness >= 0.5 ? "warning" : "info", new vscode.ThemeColor(verdict.flakiness >= 0.5 ? "list.warningForeground" : "foreground"));
        const tooltip = new vscode.MarkdownString();
        tooltip.appendMarkdown(`**${verdict.suite} › ${verdict.name}**\n\n`);
        tooltip.appendMarkdown(`${verdict.rationale}\n\n`);
        tooltip.appendMarkdown(`- 불안정도: **${percent}%** (신뢰도 ${confidenceLabel(verdict.confidence)})\n`);
        tooltip.appendMarkdown(`- 실행 ${verdict.totalRuns}회 중 ${verdict.failures}회 실패\n`);
        if (verdict.lastFailureMessage) {
            tooltip.appendMarkdown(`\n최근 실패:\n\n\`\`\`\n${verdict.lastFailureMessage.slice(0, 400)}\n\`\`\``);
        }
        item.tooltip = tooltip;
        return item;
    }
}
function confidenceLabel(confidence) {
    return { low: "낮음", medium: "보통", high: "높음" }[confidence];
}
// ── 라이선스 ──────────────────────────────────────────────
async function enterLicense(gate, provider) {
    const key = await vscode.window.showInputBox({
        title: "Flaky Test Radar 라이선스",
        prompt: "Gumroad 구매 확인 메일에 있는 라이선스 키를 붙여넣어 주세요",
        ignoreFocusOut: true,
    });
    if (!key)
        return;
    const result = await gate.activate(key);
    if (result.ok) {
        vscode.window.showInformationMessage("라이선스가 확인됐습니다. 감사합니다!");
        provider.refresh();
    }
    else {
        vscode.window.showErrorMessage(result.message);
    }
}
async function showStatus(gate) {
    vscode.window.showInformationMessage(describeEntitlement(await gate.check()));
}
function describeEntitlement(entitlement) {
    switch (entitlement.status) {
        case "trial":
            return `체험 기간 ${entitlement.daysRemaining}일 남았습니다.`;
        case "licensed":
            return entitlement.stale
                ? "라이선스 사용 중입니다. (최근 확인에 실패했지만 계속 사용하실 수 있습니다)"
                : "라이선스가 정상 확인됐습니다.";
        case "expired":
            return "체험이 끝났습니다. 계속 쓰시려면 구매해 주세요.";
        case "revoked":
            return "라이선스를 사용할 수 없습니다. 상태를 확인해 주세요.";
    }
}
// ── 설정 ──────────────────────────────────────────────────
const config = () => vscode.workspace.getConfiguration("flakyRadar");
const minRuns = () => config().get("minRuns", 2);
const maxRuns = () => config().get("maxRuns", 200);
//# sourceMappingURL=extension.js.map