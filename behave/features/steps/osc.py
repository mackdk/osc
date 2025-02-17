import os
import shutil
import tempfile
import time

import behave

from steps.common import run_in_context


class Osc:
    def __init__(self, context):
        self.temp = tempfile.mkdtemp(prefix="osc_behave_")

        if not hasattr(context, "kanku"):
            raise RuntimeError("context doesn't have kanku object set")

        self.oscrc = os.path.join(self.temp, "oscrc")
        with open(self.oscrc, "w") as f:
            f.write("[general]\n")
            f.write("\n")
            f.write(f"[https://{context.kanku.ip}]\n")
            f.write("user=Admin\n")
            f.write("pass=opensuse\n")
            f.write("credentials_mgr_class=osc.credentials.PlaintextConfigFileCredentialsManager\n")
            f.write("sslcertck=0\n")
            f.write("trusted_prj=openSUSE.org:openSUSE:Tumbleweed\n")

    def __del__(self):
        try:
            shutil.rmtree(self.temp)
        except Exception:
            pass

    def get_cmd(self, context):
        osc_cmd = context.config.userdata.get("osc", "osc")
        cmd = [osc_cmd]
        cmd += ["--config", self.oscrc]
        cmd += ["-A", f"https://{context.kanku.ip}"]
        return cmd


@behave.step("I execute osc with args \"{args}\"")
def step_impl(context, args):
    args = args.format(context=context)
    cmd = context.osc.get_cmd(context) + [args]
    cmd = " ".join(cmd)
    run_in_context(context, cmd, can_fail=True)


@behave.step('I wait for osc results for "{project}" "{package}"')
def step_impl(context, project, package):
    args = f"results {project} {package} --csv --format='%(code)s,%(dirty)s'"
    cmd = context.osc.get_cmd(context) + [args]
    cmd = " ".join(cmd)

    while True:
        # wait for a moment before checking the status even for the first time
        # for some reason, packages appear to be "broken" for a while after they get commited
        time.sleep(5)

        run_in_context(context, cmd, can_fail=True)
        results = []
        for line in context.cmd_stdout.splitlines():
            code, dirty = line.split(",")
            dirty = dirty.lower() == "true"
            results.append((code, dirty))

        if all((code == "succeeded" and not dirty for code, dirty in results)):
            # all builds have succeeded and all dirty flags are false
            break

        if any((code in ("unresolvable", "failed", "broken", "blocked", "locked", "excluded") and not dirty for code, dirty in results)):
            # failed build with dirty flag false
            raise AssertionError("Package build failed:\n" + context.cmd_stdout)
