"use strict";
/*! Copyright (c) Microsoft Corporation. All rights reserved. */
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    Object.defineProperty(o, k2, { enumerable: true, get: function() { return m[k]; } });
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || function (mod) {
    if (mod && mod.__esModule) return mod;
    var result = {};
    if (mod != null) for (var k in mod) if (k !== "default" && Object.hasOwnProperty.call(mod, k)) __createBinding(result, mod, k);
    __setModuleDefault(result, mod);
    return result;
};
var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.PythonSupport = void 0;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const vscode = __importStar(require("vscode"));
const genericErrorMessage = "Cannot start IntelliCode support for Python. See output window for more details.";
const defaultAnalyzerName = "intellisense-members";
const lstmAnalyzerName = "intellisense-members-lstm";
const lstmPylanceAnalyzerName = "intellisense-members-lstm-pylance";
const lsTypeSettingName = "languageServer";
const MPLS = "Microsoft";
const Pylance = "Pylance";
const Jedi = "Jedi";
const Node = "Node";
const PYTHON_EXTENSION_ID = "ms-python.python";
const PYLANCE_EXTENSION_ID = "ms-python.vscode-pylance";
class PythonSupport {
    constructor() {
        this.logger = () => { };
    }
    getRequestedConfig() {
        return [];
    }
    activate(api, logger) {
        return __awaiter(this, void 0, void 0, function* () {
            this.logger = logger;
            const pythonExtension = vscode.extensions.getExtension(PYTHON_EXTENSION_ID);
            if (!pythonExtension) {
                const err = "Microsoft Python extension is not installed.";
                this.logger(err);
                return Promise.reject(err);
            }
            const config = vscode.workspace.getConfiguration("python");
            if (!config) {
                this.logger("Unable to find Python configuration section.");
                return;
            }
            let ls = config.get(lsTypeSettingName);
            if (!ls || ls === "None") {
                this.logger(`Language server is set to ${ls || "undefined"}, IntelliCode is unable to continue.`);
                return;
            }
            if (ls === "Default") {
                const pylanceExtension = vscode.extensions.getExtension(PYLANCE_EXTENSION_ID);
                if (pylanceExtension) {
                    const pylanceApi = yield pylanceExtension.activate();
                    if (pylanceApi && Object.keys(pylanceApi).length > 0) {
                        ls = Pylance;
                    }
                }
                if (ls === "Default") {
                    ls = Jedi;
                }
                this.logger(`Language server is set to "Default". ${ls} is used as current language server.`);
            }
            else {
                this.logger(`Language server is set to ${ls}.`);
            }
            if (ls !== Pylance && ls !== Node) {
                this.logger("IntelliCode Python suggests to use Pylance as language server. Details about Pylance: 'https://aka.ms/vscode-pylance'.");
            }
            if (ls === MPLS) {
                return this.handlePythonExtensionV1(api, pythonExtension);
            }
            if (ls === Pylance || ls === Node) {
                return this.handlePythonExtensionV2(api, pythonExtension);
            }
        });
    }
    handlePythonExtensionV1(api, pythonExtension) {
        return __awaiter(this, void 0, void 0, function* () {
            const useDeepLearning = api.isFeatureEnabled("python.deepLearning");
            const analyzerName = useDeepLearning ? lstmAnalyzerName : defaultAnalyzerName;
            const intelliCodeAssemblyName = useDeepLearning ? "IntelliCodeForPythonLstm.dll" : "IntellicodeForPython2.dll";
            const assembly = path_1.default.join(__dirname, intelliCodeAssemblyName);
            try {
                fs_1.default.accessSync(assembly, fs_1.default.constants.F_OK);
            }
            catch (err) {
                this.logger(`Python Language Server extension assembly doesn't exist in ${assembly}. Please reinstall IntelliCode.`);
                return Promise.reject(err);
            }
            let model = yield this.acquireModel(api, analyzerName);
            if (!model && analyzerName === lstmAnalyzerName) {
                this.logger("No deep learning model available for Python, fall back to the default model.");
                model = yield this.acquireModel(api, defaultAnalyzerName);
            }
            if (!model) {
                this.logger("No model available for Python, cannot continue.");
                return;
            }
            yield this.activatePythonExtension(pythonExtension);
            const typeName = "Microsoft.PythonTools.Analysis.Pythia.LanguageServerExtensionProvider";
            const command = vscode.commands.executeCommand("python._loadLanguageServerExtension", {
                assembly,
                typeName,
                properties: {
                    modelPath: model.modelPath,
                },
            });
            if (!command) {
                this.logger("Couldn't find language server extension command. Is the installed version of Python 2018.7.0 or later?");
                return Promise.reject(new Error(genericErrorMessage));
            }
        });
    }
    handlePythonExtensionV2(api, pythonExtension) {
        return __awaiter(this, void 0, void 0, function* () {
            this.logger("Acquiring model");
            let model = yield this.acquireModel(api, lstmPylanceAnalyzerName);
            if (!model) {
                this.logger("No model v2 available for Python, trying v1.");
                model = yield this.acquireModel(api, lstmAnalyzerName);
                if (!model) {
                    this.logger("No model available for Python, cannot continue.");
                    return;
                }
            }
            this.logger("Activating Python extension");
            yield this.activatePythonExtension(pythonExtension);
            try {
                yield vscode.commands.executeCommand("python.intellicode.loadLanguageServerExtension", {
                    modelPath: model.modelPath,
                });
            }
            catch (e) {
                const message = `Language server extension command failed. Exception: ${e.stack}`;
                this.logger(message);
                return Promise.reject(new Error(message));
            }
        });
    }
    activatePythonExtension(pythonExtension) {
        return __awaiter(this, void 0, void 0, function* () {
            if (!pythonExtension.isActive) {
                yield pythonExtension.activate();
            }
            yield pythonExtension.exports.ready;
        });
    }
    acquireModel(api, analyzerName) {
        return __awaiter(this, void 0, void 0, function* () {
            const model = api.ModelAcquisitionService.getModelProvider("python", analyzerName).getModelAsync();
            if (model) {
                const modelJson = JSON.stringify(model);
                this.logger(`vs-intellicode-python was passed a model: ${modelJson}.`);
            }
            return model;
        });
    }
}
exports.PythonSupport = PythonSupport;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidnNjb2RlLWludGVsbGljb2RlLXB5dGhvbi5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbIi4uL3NyYy92c2NvZGUtaW50ZWxsaWNvZGUtcHl0aG9uLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7QUFBQSxnRUFBZ0U7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7QUFHaEUsNENBQW9CO0FBQ3BCLGdEQUF3QjtBQUN4QiwrQ0FBaUM7QUFFakMsTUFBTSxtQkFBbUIsR0FBVyxrRkFBa0YsQ0FBQztBQUN2SCxNQUFNLG1CQUFtQixHQUFHLHNCQUFzQixDQUFDO0FBQ25ELE1BQU0sZ0JBQWdCLEdBQUcsMkJBQTJCLENBQUM7QUFDckQsTUFBTSx1QkFBdUIsR0FBRyxtQ0FBbUMsQ0FBQztBQUVwRSxNQUFNLGlCQUFpQixHQUFHLGdCQUFnQixDQUFDO0FBRTNDLE1BQU0sSUFBSSxHQUFHLFdBQVcsQ0FBQztBQUV6QixNQUFNLE9BQU8sR0FBRyxTQUFTLENBQUM7QUFFMUIsTUFBTSxJQUFJLEdBQUcsTUFBTSxDQUFDO0FBRXBCLE1BQU0sSUFBSSxHQUFHLE1BQU0sQ0FBQztBQUVwQixNQUFNLG1CQUFtQixHQUFHLGtCQUFrQixDQUFDO0FBRS9DLE1BQU0sb0JBQW9CLEdBQUcsMEJBQTBCLENBQUM7QUFFeEQsTUFBYSxhQUFhO0lBQTFCO1FBQ1ksV0FBTSxHQUEwQixHQUFHLEVBQUUsR0FBRSxDQUFDLENBQUM7SUFpS3JELENBQUM7SUEvSkcsa0JBQWtCO1FBRWQsT0FBTyxFQUFFLENBQUM7SUFDZCxDQUFDO0lBRUssUUFBUSxDQUFDLEdBQXFCLEVBQUUsTUFBNkI7O1lBQy9ELElBQUksQ0FBQyxNQUFNLEdBQUcsTUFBTSxDQUFDO1lBR3JCLE1BQU0sZUFBZSxHQUFHLE1BQU0sQ0FBQyxVQUFVLENBQUMsWUFBWSxDQUFDLG1CQUFtQixDQUFDLENBQUM7WUFDNUUsSUFBSSxDQUFDLGVBQWUsRUFBRTtnQkFDbEIsTUFBTSxHQUFHLEdBQUcsOENB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