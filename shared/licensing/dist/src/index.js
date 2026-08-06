"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.DAY_MS = exports.verifyLicense = exports.describeRevocation = exports.LicenseGate = void 0;
exports.memento = memento;
exports.memoryStorage = memoryStorage;
var gate_1 = require("./gate");
Object.defineProperty(exports, "LicenseGate", { enumerable: true, get: function () { return gate_1.LicenseGate; } });
Object.defineProperty(exports, "describeRevocation", { enumerable: true, get: function () { return gate_1.describeRevocation; } });
var gumroad_1 = require("./gumroad");
Object.defineProperty(exports, "verifyLicense", { enumerable: true, get: function () { return gumroad_1.verifyLicense; } });
var types_1 = require("./types");
Object.defineProperty(exports, "DAY_MS", { enumerable: true, get: function () { return types_1.DAY_MS; } });
/**
 * VS Code의 `context.globalState`를 Storage로 감싼다.
 *
 * 확장에서:
 *   const gate = new LicenseGate({ productId }, memento(context.globalState));
 *
 * globalState를 쓰는 이유는 라이선스가 워크스페이스가 아니라 사용자에게 귀속되기 때문이다.
 */
function memento(state) {
    return {
        get: (key) => state.get(key),
        set: async (key, value) => {
            await state.update(key, value);
        },
    };
}
/** 테스트·개발용 인메모리 저장소. */
function memoryStorage(initial = {}) {
    const data = { ...initial };
    return {
        get: (key) => data[key],
        set: async (key, value) => {
            data[key] = value;
        },
        dump: () => ({ ...data }),
    };
}
//# sourceMappingURL=index.js.map