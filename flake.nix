{
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
  outputs = { self, nixpkgs, ... }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
    in
    {
      devShells = forAllSystems (pkgs: {
          default = pkgs.mkShell {
            packages = with pkgs; [
              yq-go
              gettext
              jq
              just
              (python3.withPackages (ps: with ps; [ pyyaml jsonschema ]))
            ];
          };
        });

      apps = forAllSystems (pkgs: let
        pythonEnv = pkgs.python3.withPackages (ps: with ps; [ pyyaml jsonschema ]);
        runtimeInputs = with pkgs; [
          bash
          yq-go
          gettext
          jq
          pythonEnv
        ];
        bashBin = "${pkgs.bash}/bin/bash";

        validateCmd = ''
          # Script syntax checks
          python -c "import ast; ast.parse(open('./generate.py').read())"
          ${bashBin} -n ./install.sh

          # Protocol file presence checks
          test -f ./SETTINGS.yaml
          test -f ./TEAM.yaml
          test -f ./schemas/agent-runtime.schema.json
          test -f ./schemas/team.schema.json

          # Basic protocol shape checks
          yq -e '.version == 1' ./SETTINGS.yaml
          yq -e '.version == 1' ./TEAM.yaml
          yq -e '.agents.order | type == "!!seq"' ./TEAM.yaml
          yq -e '.skills.order | type == "!!seq"' ./TEAM.yaml
          yq -e '.rules.order | type == "!!seq"' ./TEAM.yaml

          # OpenCode base config must exist and be valid JSON
          test -f ./opencode/config.json
          jq empty ./opencode/config.json

          # JSON Schema validation for protocol files
          python <<'PY'
          import json
          from pathlib import Path

          import yaml
          from jsonschema import validate

          root = Path(".")
          settings_data = yaml.safe_load((root / "SETTINGS.yaml").read_text())
          team_data = yaml.safe_load((root / "TEAM.yaml").read_text())
          settings_schema = json.loads((root / "schemas/agent-runtime.schema.json").read_text())
          team_schema = json.loads((root / "schemas/team.schema.json").read_text())

          validate(instance=settings_data, schema=settings_schema)
          validate(instance=team_data, schema=team_schema)

          # TEAM referenced files must exist on disk.
          for agent_id in team_data["agents"]["order"]:
              instruction_file = team_data["agents"]["items"][agent_id]["instruction_file"]
              if not (root / instruction_file).is_file():
                  raise FileNotFoundError(f"Missing agent instruction file: {instruction_file}")

          for skill_id in team_data["skills"]["order"]:
              instruction_file = team_data["skills"]["items"][skill_id]["instruction_file"]
              if not (root / instruction_file).is_file():
                  raise FileNotFoundError(f"Missing skill instruction file: {instruction_file}")

          for rule_id in team_data["rules"]["order"]:
              source_file = team_data["rules"]["items"][rule_id]["source_file"]
              if not (root / source_file).is_file():
                  raise FileNotFoundError(f"Missing rule source file: {source_file}")
          PY
        '';

        mkAppScript = name: text:
          pkgs.writeShellApplication {
            inherit name runtimeInputs text;
          };
      in {
          build = {
            type = "app";
            program = "${mkAppScript "build" ''
              set -euo pipefail
              test -f ./generate.py || { echo "Run this command from the repository root."; exit 1; }
              python ./generate.py
            ''}/bin/build";
            meta.description = "Generate Claude, Codex, and OpenCode build artifacts from the authored protocol files.";
          };

          validate = {
            type = "app";
            program = "${mkAppScript "validate" ''
              set -euo pipefail
              test -f ./generate.py || { echo "Run this command from the repository root."; exit 1; }
              ${validateCmd}
            ''}/bin/validate";
            meta.description = "Validate scripts and protocol files.";
          };

          check = {
            type = "app";
            program = "${mkAppScript "check" ''
              set -euo pipefail
              test -f ./generate.py || { echo "Run this command from the repository root."; exit 1; }
              ${validateCmd}
              python ./generate.py
            ''}/bin/check";
            meta.description = "Run validation and generation together.";
          };

          install = {
            type = "app";
            program = "${mkAppScript "install" ''
              set -euo pipefail
              test -f ./install.sh || { echo "Run this command from the repository root."; exit 1; }
              ${validateCmd}
              ${bashBin} ./install.sh
            ''}/bin/install";
            meta.description = "Install generated artifacts into Claude, Codex, and OpenCode config directories.";
          };
        });

      checks = forAllSystems (pkgs: let
        pythonEnv = pkgs.python3.withPackages (ps: with ps; [ pyyaml jsonschema ]);
        runtimeInputs = with pkgs; [
          bash
          yq-go
          gettext
          jq
          pythonEnv
        ];
        bashBin = "${pkgs.bash}/bin/bash";

        validateCmd = ''
          python -c "import ast; ast.parse(open('./generate.py').read())"
          ${bashBin} -n ./install.sh
          test -f ./SETTINGS.yaml
          test -f ./TEAM.yaml
          test -f ./schemas/agent-runtime.schema.json
          test -f ./schemas/team.schema.json
          yq -e '.version == 1' ./SETTINGS.yaml
          yq -e '.version == 1' ./TEAM.yaml
          yq -e '.agents.order | type == "!!seq"' ./TEAM.yaml
          yq -e '.skills.order | type == "!!seq"' ./TEAM.yaml
          yq -e '.rules.order | type == "!!seq"' ./TEAM.yaml

          python <<'PY'
          import json
          from pathlib import Path

          import yaml
          from jsonschema import validate

          root = Path(".")
          settings_data = yaml.safe_load((root / "SETTINGS.yaml").read_text())
          team_data = yaml.safe_load((root / "TEAM.yaml").read_text())
          settings_schema = json.loads((root / "schemas/agent-runtime.schema.json").read_text())
          team_schema = json.loads((root / "schemas/team.schema.json").read_text())

          validate(instance=settings_data, schema=settings_schema)
          validate(instance=team_data, schema=team_schema)

          # TEAM referenced files must exist on disk.
          for agent_id in team_data["agents"]["order"]:
              instruction_file = team_data["agents"]["items"][agent_id]["instruction_file"]
              if not (root / instruction_file).is_file():
                  raise FileNotFoundError(f"Missing agent instruction file: {instruction_file}")

          for skill_id in team_data["skills"]["order"]:
              instruction_file = team_data["skills"]["items"][skill_id]["instruction_file"]
              if not (root / instruction_file).is_file():
                  raise FileNotFoundError(f"Missing skill instruction file: {instruction_file}")

          for rule_id in team_data["rules"]["order"]:
              source_file = team_data["rules"]["items"][rule_id]["source_file"]
              if not (root / source_file).is_file():
                  raise FileNotFoundError(f"Missing rule source file: {source_file}")
          PY
        '';

        mkCheck = name: text:
          pkgs.runCommand name { nativeBuildInputs = runtimeInputs; src = ./.; } ''
            mkdir -p "$TMPDIR/repo"
            cp -R "$src"/. "$TMPDIR/repo"
            chmod -R u+w "$TMPDIR/repo"
            cd "$TMPDIR/repo"
            ${text}
            touch "$out"
          '';
      in {
        validate = mkCheck "agent-team-validate-check" ''
          set -euxo pipefail
          ${validateCmd}
        '';

        build = mkCheck "agent-team-build-check" ''
          set -euxo pipefail
          ${validateCmd}
          python ./generate.py
        '';
      });
    };
}
