/*---------------------------------------------------------------------------------------------
 *  Copyright (c) Microsoft Corporation. All rights reserved.
 *  Licensed under the MIT License. See License.txt in the project root for license information.
 *--------------------------------------------------------------------------------------------*/

//@ts-check
"use strict";

//@ts-check
/** @typedef {import('webpack').Configuration} WebpackConfig **/

const path = require("path");
const webpack = require("webpack");
const CopyPlugin = require("copy-webpack-plugin");

/** @type WebpackConfig */
const webExtensionConfig = {
    mode: "none", // this leaves the source code as close as possible to the original (when packaging we set this to 'production')
    target: "webworker", // extensions run in a webworker context
    entry: {
        extension: "./src/web/extension.ts",
    },
    output: {
        filename: "[name].js",
        path: path.join(__dirname, "./dist/web"),
        libraryTarget: "commonjs",
        devtoolModuleFilenameTemplate: "../../[resource-path]",
    },
    resolve: {
        mainFields: ["browser", "module", "main"], // look for `browser` entry point in imported node modules
        extensions: [".ts", ".js"], // support ts-files and js-files
        alias: {
            // provides alternate implementation for node module and source files
        },
        fallback: {
            // Webpack 5 no longer polyfills Node.js core modules automatically.
            // see https://webpack.js.org/configuration/resolve/#resolvefallback
            // for the list of Node.js core module polyfills.
            assert: require.resolve("assert"),
            path: require.resolve("path-browserify"),
            crypto: require.resolve("crypto-browserify"),
            zlib: require.resolve("browserify-zlib"),
            stream: require.resolve("stream-browserify"),
        },
    },
    module: {
        rules: [
            {
                test: /\.ts$/,
                exclude: /node_modules/,
                use: [
                    {
                        loader: "ts-loader",
                    },
                ],
            },
        ],
    },
    plugins: [
        new webpack.ProvidePlugin({
            process: "process/browser", // provide a shim for the global `process` variable
            Buffer: ["buffer", "Buffer"],
        }),
    ],
    externals: {
        vscode: "commonjs vscode", // ignored because it doesn't exist
        // These dependencies are ignored because we don't use them, and App Insights has try-catch protecting their loading if they don't exist
        // See: https://github.com/microsoft/vscode-extension-telemetry/issues/41#issuecomment-598852991
        "applicationinsights-native-metrics": "commonjs applicationinsights-native-metrics",
        "@opentelemetry/tracing": "commonjs @opentelemetry/tracing",
    },
    performance: {
        hints: false,
    },
    devtool: "nosources-source-map", // create a source map that points to the original source file
    infrastructureLogging: {
        level: "log", // enables logging required for problem matchers
    },
};

module.exports = [webExtensionConfig];
