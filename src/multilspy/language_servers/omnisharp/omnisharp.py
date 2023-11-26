"""
Provides C# specific instantiation of the LanguageServer class. Contains various configurations and settings specific to C#.
"""

import asyncio
import json
import logging
import os
import pathlib
import stat
from contextlib import asynccontextmanager
from typing import AsyncIterator, Iterable

from monitors4codegen.multilspy.multilspy_logger import MultilspyLogger
from monitors4codegen.multilspy.language_server import LanguageServer
from monitors4codegen.multilspy.lsp_protocol_handler.server import ProcessLaunchInfo
from monitors4codegen.multilspy.lsp_protocol_handler.lsp_types import InitializeParams
from monitors4codegen.multilspy.multilspy_config import MultilspyConfig
from monitors4codegen.multilspy.multilspy_exceptions import MultilspyException
from monitors4codegen.multilspy.multilspy_utils import FileUtils, PlatformUtils, PlatformId, DotnetVersion


def breadth_first_file_scan(root) -> Iterable[str]:
    """
    This function was obtained from https://stackoverflow.com/questions/49654234/is-there-a-breadth-first-search-option-available-in-os-walk-or-equivalent-py
    It traverses the directory tree in breadth first order.
    """
    dirs = [root]
    # while we has dirs to scan
    while len(dirs):
        next_dirs = []
        for parent in dirs:
            # scan each dir
            for f in os.listdir(parent):
                # if there is a dir, then save for next ittr
                # if it  is a file then yield it (we'll return later)
                ff = os.path.join(parent, f)
                if os.path.isdir(ff):
                    next_dirs.append(ff)
                else:
                    yield ff

        # once we've done all the current dirs then
        # we set up the next itter as the child dirs
        # from the current itter.
        dirs = next_dirs


def find_least_depth_sln_file(root_dir) -> str:
    for filename in breadth_first_file_scan(root_dir):
        if filename.endswith(".sln"):
            return filename
    return None


class OmniSharp(LanguageServer):
    """
    Provides C# specific instantiation of the LanguageServer class. Contains various configurations and settings specific to C#.
    """

    def __init__(self, config: MultilspyConfig, logger: MultilspyLogger, repository_root_path: str):
        """
        Creates an OmniSharp instance. This class is not meant to be instantiated directly. Use LanguageServer.create() instead.
        """
        omnisharp_executable_path, dll_path = self.setupRuntimeDependencies(logger, config)

        slnfilename = find_least_depth_sln_file(repository_root_path)
        if slnfilename is None:
            logger.log("No *.sln file found in repository", logging.ERROR)
            raise MultilspyException("No SLN file found in repository")

        cmd = " ".join(
            [
                omnisharp_executable_path,
                "-lsp",
                "--encoding",
                "ascii",
                "-z",
                "-s",
                slnfilename,
                "--hostPID",
                str(os.getpid()),
                "DotNet:enablePackageRestore=false",
                "--loglevel",
                "trace",
                "--plugin",
                dll_path,
                "FileOptions:SystemExcludeSearchPatterns:0=**/.git",
                "FileOptions:SystemExcludeSearchPatterns:1=**/.svn",
                "FileOptions:SystemExcludeSearchPatterns:2=**/.hg",
                "FileOptions:SystemExcludeSearchPatterns:3=**/CVS",
                "FileOptions:SystemExcludeSearchPatterns:4=**/.DS_Store",
                "FileOptions:SystemExcludeSearchPatterns:5=**/Thumbs.db",
                "RoslynExtensionsOptions:EnableAnalyzersSupport=true",
                "FormattingOptions:EnableEditorConfigSupport=true",
                "RoslynExtensionsOptions:EnableImportCompletion=true",
                "Sdk:IncludePrereleases=true",
                "RoslynExtensionsOptions:AnalyzeOpenDocumentsOnly=true",
                "formattingOptions:useTabs=false",
                "formattingOptions:tabSize=4",
                "formattingOptions:indentationSize=4",
            ]
        )
        super().__init__(
            config, logger, repository_root_path, ProcessLaunchInfo(cmd=cmd, cwd=repository_root_path), "csharp"
        )

        self.definition_available = asyncio.Event()
        self.references_available = asyncio.Event()

    def _get_initialize_params(self, repository_absolute_path: str) -> InitializeParams:
        """
        Returns the initialize params for the Rust Analyzer Language Server.
        """
        with open(os.path.join(os.path.dirname(__file__), "initialize_params.json"), "r") as f:
            d = json.load(f)

        del d["_description"]

        d["processId"] = os.getpid()
        assert d["rootPath"] == "$rootPath"
        d["rootPath"] = repository_absolute_path

        assert d["rootUri"] == "$rootUri"
        d["rootUri"] = pathlib.Path(repository_absolute_path).as_uri()

        assert d["workspaceFolders"][0]["uri"] == "$uri"
        d["workspaceFolders"][0]["uri"] = pathlib.Path(repository_absolute_path).as_uri()

        assert d["workspaceFolders"][0]["name"] == "$name"
        d["workspaceFolders"][0]["name"] = os.path.basename(repository_absolute_path)

        return d

    def setupRuntimeDependencies(self, logger: MultilspyLogger, config: MultilspyConfig) -> tuple[str, str]:
        """
        Setup runtime dependencies for OmniSharp.
        """
        platform_id = PlatformUtils.get_platform_id()
        dotnet_version = PlatformUtils.get_dotnet_version()

        with open(os.path.join(os.path.dirname(__file__), "runtime_dependencies.json"), "r") as f:
            d = json.load(f)
            del d["_description"]

        assert platform_id in [
            PlatformId.LINUX_x64,
            PlatformId.WIN_x64,
        ], "Only linux-x64 and win-x64 platform is supported for in multilspy at the moment"
        assert dotnet_version in [
            DotnetVersion.V6,
            DotnetVersion.V7,
        ], "Only dotnet version 6 and 7 are supported in multilspy at the moment"

        # TODO: Do away with this assumption
        # Currently, runtime binaries are not available for .Net 7. Hence, we assume .Net 6 runtime binaries to be compatible with .Net 7
        if dotnet_version == DotnetVersion.V7:
            dotnet_version = DotnetVersion.V6

        runtime_dependencies = d["runtimeDependencies"]
        runtime_dependencies = [
            dependency for dependency in runtime_dependencies if dependency["platformId"] == platform_id.value
        ]
        runtime_dependencies = [
            dependency
            for dependency in runtime_dependencies
            if not ("dotnet_version" in dependency) or dependency["dotnet_version"] == dotnet_version.value
        ]
        assert len(runtime_dependencies) == 2
        runtime_dependencies = {
            runtime_dependencies[0]["id"]: runtime_dependencies[0],
            runtime_dependencies[1]["id"]: runtime_dependencies[1],
        }

        assert "OmniSharp" in runtime_dependencies
        assert "RazorOmnisharp" in runtime_dependencies

        omnisharp_ls_dir = os.path.join(os.path.dirname(__file__), "static", "OmniSharp")
        if not os.path.exists(omnisharp_ls_dir):
            os.makedirs(omnisharp_ls_dir)
            FileUtils.download_and_extract_archive(
                logger, runtime_dependencies["OmniSharp"]["url"], omnisharp_ls_dir, "zip"
            )
        omnisharp_executable_path = os.path.join(omnisharp_ls_dir, runtime_dependencies["OmniSharp"]["binaryName"])
        assert os.path.exists(omnisharp_executable_path)
        os.chmod(omnisharp_executable_path, stat.S_IEXEC)

        razor_omnisharp_ls_dir = os.path.join(os.path.dirname(__file__), "static", "RazorOmnisharp")
        if not os.path.exists(razor_omnisharp_ls_dir):
            os.makedirs(razor_omnisharp_ls_dir)
            FileUtils.download_and_extract_archive(
                logger, runtime_dependencies["RazorOmnisharp"]["url"], razor_omnisharp_ls_dir, "zip"
            )
        razor_omnisharp_dll_path = os.path.join(
            razor_omnisharp_ls_dir, runtime_dependencies["RazorOmnisharp"]["dll_path"]
        )
        assert os.path.exists(razor_omnisharp_dll_path)

        return omnisharp_executable_path, razor_omnisharp_dll_path

    @asynccontextmanager
    async def start_server(self) -> AsyncIterator["OmniSharp"]:
        """
        Starts the Rust Analyzer Language Server, waits for the server to be ready and yields the LanguageServer instance.

        Usage:
        ```
        async with lsp.start_server():
            # LanguageServer has been initialized and ready to serve requests
            await lsp.request_definition(...)
            await lsp.request_references(...)
            # Shutdown the LanguageServer on exit from scope
        # LanguageServer has been shutdown
        """

        async def register_capability_handler(params):
            assert "registrations" in params
            for registration in params["registrations"]:
                if registration["method"] == "textDocument/definition":
                    self.definition_available.set()
                if registration["method"] == "textDocument/references":
                    self.references_available.set()
                if registration["method"] == "textDocument/completion":
                    self.completions_available.set()

        async def lang_status_handler(params):
            # TODO: Should we wait for
            # server -> client: {'jsonrpc': '2.0', 'method': 'language/status', 'params': {'type': 'ProjectStatus', 'message': 'OK'}}
            # Before proceeding?
            # if params["type"] == "ServiceReady" and params["message"] == "ServiceReady":
            #     self.service_ready_event.set()
            pass

        async def execute_client_command_handler(params):
            return []

        async def do_nothing(params):
            return

        async def check_experimental_status(params):
            if params["quiescent"] == True:
                self.server_ready.set()

        async def window_log_message(msg):
            self.logger.log(f"LSP: window/logMessage: {msg}", logging.INFO)

        async def workspace_configuration_handler(params):
            # TODO: We do not know the appropriate way to handle this request. Should ideally contact the OmniSharp dev team
            return [
                {
                    "RoslynExtensionsOptions": {
                        "EnableDecompilationSupport": False,
                        "EnableAnalyzersSupport": True,
                        "EnableImportCompletion": True,
                        "EnableAsyncCompletion": False,
                        "DocumentAnalysisTimeoutMs": 30000,
                        "DiagnosticWorkersThreadCount": 18,
                        "AnalyzeOpenDocumentsOnly": True,
                        "InlayHintsOptions": {
                            "EnableForParameters": False,
                            "ForLiteralParameters": False,
                            "ForIndexerParameters": False,
                            "ForObjectCreationParameters": False,
                            "ForOtherParameters": False,
                            "SuppressForParametersThatDifferOnlyBySuffix": False,
                            "SuppressForParametersThatMatchMethodIntent": False,
                            "SuppressForParametersThatMatchArgumentName": False,
                            "EnableForTypes": False,
                            "ForImplicitVariableTypes": False,
                            "ForLambdaParameterTypes": False,
                            "ForImplicitObjectCreation": False,
                        },
                        "LocationPaths": None,
                    },
                    "FormattingOptions": {
                        "OrganizeImports": False,
                        "EnableEditorConfigSupport": True,
                        "NewLine": "\n",
                        "UseTabs": False,
                        "TabSize": 4,
                        "IndentationSize": 4,
                        "SpacingAfterMethodDeclarationName": False,
                        "SeparateImportDirectiveGroups": False,
                        "SpaceWithinMethodDeclarationParenthesis": False,
                        "SpaceBetweenEmptyMethodDeclarationParentheses": False,
                        "SpaceAfterMethodCallName": False,
                        "SpaceWithinMethodCallParentheses": False,
                        "SpaceBetweenEmptyMethodCallParentheses": False,
                        "SpaceAfterControlFlowStatementKeyword": True,
                        "SpaceWithinExpressionParentheses": False,
                        "SpaceWithinCastParentheses": False,
                        "SpaceWithinOtherParentheses": False,
                        "SpaceAfterCast": False,
                        "SpaceBeforeOpenSquareBracket": False,
                        "SpaceBetweenEmptySquareBrackets": False,
                        "SpaceWithinSquareBrackets": False,
                        "SpaceAfterColonInBaseTypeDeclaration": True,
                        "SpaceAfterComma": True,
                        "SpaceAfterDot": False,
                        "SpaceAfterSemicolonsInForStatement": True,
                        "SpaceBeforeColonInBaseTypeDeclaration": True,
                        "SpaceBeforeComma": False,
                        "SpaceBeforeDot": False,
                        "SpaceBeforeSemicolonsInForStatement": False,
                        "SpacingAroundBinaryOperator": "single",
                        "IndentBraces": False,
                        "IndentBlock": True,
                        "IndentSwitchSection": True,
                        "IndentSwitchCaseSection": True,
                        "IndentSwitchCaseSectionWhenBlock": True,
                        "LabelPositioning": "oneLess",
                        "WrappingPreserveSingleLine": True,
                        "WrappingKeepStatementsOnSingleLine": True,
                        "NewLinesForBracesInTypes": True,
                        "NewLinesForBracesInMethods": True,
                        "NewLinesForBracesInProperties": True,
                        "NewLinesForBracesInAccessors": True,
                        "NewLinesForBracesInAnonymousMethods": True,
                        "NewLinesForBracesInControlBlocks": True,
                        "NewLinesForBracesInAnonymousTypes": True,
                        "NewLinesForBracesInObjectCollectionArrayInitializers": True,
                        "NewLinesForBracesInLambdaExpressionBody": True,
                        "NewLineForElse": True,
                        "NewLineForCatch": True,
                        "NewLineForFinally": True,
                        "NewLineForMembersInObjectInit": True,
                        "NewLineForMembersInAnonymousTypes": True,
                        "NewLineForClausesInQuery": True,
                    },
                    "FileOptions": {
                        "SystemExcludeSearchPatterns": [
                            "**/node_modules/**/*",
                            "**/bin/**/*",
                            "**/obj/**/*",
                            "**/.git/**/*",
                            "**/.git",
                            "**/.svn",
                            "**/.hg",
                            "**/CVS",
                            "**/.DS_Store",
                            "**/Thumbs.db",
                        ],
                        "ExcludeSearchPatterns": [],
                    },
                    "RenameOptions": {
                        "RenameOverloads": False,
                        "RenameInStrings": False,
                        "RenameInComments": False,
                    },
                    "ImplementTypeOptions": {
                        "InsertionBehavior": 0,
                        "PropertyGenerationBehavior": 0,
                    },
                    "DotNetCliOptions": {"LocationPaths": None},
                    "Plugins": {"LocationPaths": None},
                }
            ]

        self.server.on_request("client/registerCapability", register_capability_handler)
        self.server.on_notification("language/status", lang_status_handler)
        self.server.on_notification("window/logMessage", window_log_message)
        self.server.on_request("workspace/executeClientCommand", execute_client_command_handler)
        self.server.on_notification("$/progress", do_nothing)
        self.server.on_notification("textDocument/publishDiagnostics", do_nothing)
        self.server.on_notification("language/actionableNotification", do_nothing)
        self.server.on_notification("experimental/serverStatus", check_experimental_status)
        self.server.on_request("workspace/configuration", workspace_configuration_handler)

        async with super().start_server():
            self.logger.log("Starting OmniSharp server process", logging.INFO)
            await self.server.start()
            initialize_params = self._get_initialize_params(self.repository_root_path)

            self.logger.log(
                "Sending initialize request from LSP client to LSP server and awaiting response",
                logging.INFO,
            )
            init_response = await self.server.send.initialize(initialize_params)
            self.server.notify.initialized({})
            with open(os.path.join(os.path.dirname(__file__), "workspace_did_change_configuration.json"), "r") as f:
                self.server.notify.workspace_did_change_configuration({
                    "settings": json.load(f)
                })
            assert "capabilities" in init_response
            if (
                "definitionProvider" in init_response["capabilities"]
                and init_response["capabilities"]["definitionProvider"]
            ):
                self.definition_available.set()
            if (
                "referencesProvider" in init_response["capabilities"]
                and init_response["capabilities"]["referencesProvider"]
            ):
                self.references_available.set()

            await self.definition_available.wait()
            await self.references_available.wait()

            yield self

            await self.server.shutdown()
            await self.server.stop()
