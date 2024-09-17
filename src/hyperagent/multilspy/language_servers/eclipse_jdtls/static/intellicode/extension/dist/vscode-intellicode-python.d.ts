/*! Copyright (c) Microsoft Corporation. All rights reserved. */
import * as vsi from "@vsintellicode/vscode-intellicode-api";
export declare class PythonSupport implements vsi.IIntelliCodeLanguageSupport {
    private logger;
    getRequestedConfig(): vsi.IRequestedConfigSetting[];
    activate(api: vsi.IIntelliCode, logger: (str: string) => void): Promise<void>;
    private handlePythonExtensionV1;
    private handlePythonExtensionV2;
    private activatePythonExtension;
    private acquireModel;
}
