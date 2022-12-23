import neovim
import os
import re
import subprocess
import tempfile
import enum
import functools
import ast
import logging

try:
    from accessible_output2.outputs.auto import Auto

    AO2 = Auto()
except ImportError:
    AO2 = None

from .py_ast import PrettyReader

# Logging config
logger = logging.getLogger("nvsr")


def setup_logger():
    _handler = logging.FileHandler(
        os.path.join(tempfile.gettempdir(), "nvsr.log"), "a+"
    )
    _handler.setFormatter(
        logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )  # noqa
    )
    logger.addHandler(_handler)
    logger.setLevel(logging.DEBUG)


COMPARISONS = {
    " < ": "less than",
    " > ": "greater than",
    " >= ": "greater than or equal to",
    " <= ": "less than or equal to",
    " == ": "is equal to",
    " && ": "and",
    " || ": "or",
}

STANDARD = {
    ",": ", comma, ",
    ".": ", dot, ",
    ":": ", colon, ",
    "\n": ", newline, ",
}

SPACES = {" ": " space ", " ": " no-break space ", "\t": " tab "}

BRACKET_PAIRINGS = {
    "(": ", open paren, ",
    ")": ", close paren, ",
    "[": ", open bracket, ",
    "]": ", close bracket, ",
    "{": ", open curly, ",
    "}": ", close curly, ",
    "<": ", open angle, ",
    ">": ", close angle, ",
}

GENERIC_BIN_OPS = {
    "->": "stab",
    ">=>": "fish",
    "<=>": "spaceship",
    "=>": "fat arrow",
    "===": "triple equals",
    "++": "increment",
    "--": "decrement",
    "+=": "add with",
    "-=": "subtract with",
    "/=": "divide with",
    "*=": "multiply with",
    "?:": "elvis",
}


def requires_option(option):
    def decorator(fn):
        @functools.wraps(fn)
        def inner(self, *args, **kwargs):
            if self.get_option(option):
                return fn(self, *args, **kwargs)

        return inner

    return decorator


@neovim.plugin
class Main(object):
    class Options(enum.Enum):
        ENABLE_AT_STARTUP = ("enable_at_startup", True)
        INTERPRET_GENERIC_INFIX = ("interpet_generic_infix", False)
        SPEAK_BRACKETS = ("speak_brackets", False)
        SPEAK_KEYPRESSES = ("speak_keypresses", True)
        SPEAK_WORDS = ("speak_words", True)
        SPEAK_MODE_TRANSITIONS = ("speak_mode_transitions", True)
        SPEAK_COMPLETIONS = ("speak_completions", True)
        AUTO_SPEAK_LINE = ("auto_speak_line", True)
        AUTO_SPEAK_OUTPUT = ("auto_speak_output", True)
        INDENT_STATUS = ("speak_indent", False)
        PITCH_MULTIPLIER = ("pitch_multiplier", 1)
        SPEED = ("speak_speed", 350)
        USE_ESPEAK = ("use_espeak", False)
        USE_AO2 = ("use_ao2", True)
        SPEAK_VOICE = ("speak_voice", "")
        ENABLE_LOGGING = ("enable_logging", False)

    def __init__(self, vim):
        self.vim = vim
        self.last_spoken = ""
        self.enabled = self.get_option(self.Options.ENABLE_AT_STARTUP)
        if self.get_option(self.Options.ENABLE_LOGGING):
            setup_logger()
        self.literal_stack = []
        self.vim.api.set_var("ignorecursorevent", False)
        self.cursor_pos = self.vim.api.win_get_cursor(self.vim.current.window)
        self.current_line = self.vim.current.line
        self.outvar = "nvsr_outvar"

    def get_option(self, option):
        name, default = option.value
        val = self.vim.vars.get(name)
        if val is None:
            return default
        return val

    def get_indent_level(self, line: str) -> int:
        """
        Given a line, return the indentation level
        """
        whitespaces = 1
        if self.vim.api.get_option("expandtab"):
            whitespaces = self.vim.api.get_option("shiftwidth")

        leading_spaces = len(line) - len(line.lstrip())

        return leading_spaces // whitespaces

    def get_current_selection(self) -> list[str]:
        """
        Returns the current highlighted selection
        """
        buf = self.vim.current.buffer
        line_start, col_start = buf.mark("<")
        line_end, col_end = buf.mark(">")

        lines = self.vim.api.buf_get_lines(buf, line_start - 1, line_end, True)

        if len(lines) == 1:
            lines[0] = lines[0][col_start:col_end]
        else:
            lines[0] = lines[0][col_start:]
            lines[-1] = lines[-1][:col_end]

        return lines

    def call_say(self, txt: str, speed=None, pitch=None, literal=False, stop=True):
        voice = self.get_option(self.Options.SPEAK_VOICE)

        if self.get_option(self.Options.USE_ESPEAK):
            args = ["espeak"]
            if voice:
                args += ["-v", voice]
            if pitch:
                args += ["-p", str(pitch)]
            if speed:
                args += ["-s", str(speed)]
            if literal:
                txt = " ".join(txt)
            args.append(txt)
        elif self.get_option(self.Options.USE_AO2) and AO2:
            AO2.output(txt, interrupt=stop)
            return
        else:
            args = ["say"]
            if voice:
                args += ["-v", voice]
            if pitch:
                txt = f"[[ pbas +{pitch}]] {txt}"
            if speed:
                args += ["-r", str(speed)]
            if literal:
                txt = f"[[ char LTRL ]] {txt}"
            if stop:
                txt = f"{txt}, STOP."
            args.append(txt)

        if self.enabled:
            logger.debug(f"Saying '{txt}'")
            subprocess.run(args)

    def speak(
        self,
        txt: str,
        brackets=None,
        generic=None,
        standard=True,
        speed=None,
        indent_status=None,
        newline=False,
        literal=False,
        stop=True,
    ):

        if brackets is None:
            brackets = self.get_option(self.Options.SPEAK_BRACKETS)

        if generic is None:
            generic = self.get_option(self.Options.INTERPRET_GENERIC_INFIX)

        if speed is None:
            speed = self.get_option(self.Options.SPEED)

        if indent_status is None:
            indent_status = self.get_option(self.Options.INDENT_STATUS)

        indent_level = self.get_indent_level(txt)
        pitch_mod = indent_level * self.get_option(self.Options.PITCH_MULTIPLIER)

        if literal:
            self.call_say(txt, speed=speed, literal=literal)
        else:
            if generic:
                for (target, replacement) in GENERIC_BIN_OPS.items():
                    txt = txt.replace(target, f" {replacement} ")

            if standard:
                for (target, replacement) in {**STANDARD, **COMPARISONS}.items():
                    txt = txt.replace(target, f" {replacement} ")

            if brackets:
                for (target, replacement) in BRACKET_PAIRINGS.items():
                    txt = txt.replace(target, f" {replacement} ")

            if txt.isspace():
                for (target, replacement) in SPACES.items():
                    txt = txt.replace(target, f" {replacement} ")

            if indent_status:
                txt = f"indent {indent_level}, {txt}"
            self.call_say(txt, speed=speed, pitch=pitch_mod, stop=stop)

    def explain(self, code: str, line=True) -> str:
        try:
            top_node = ast.parse(code)

            explained = PrettyReader().visit(top_node)
        except SyntaxError as e:
            explained = f"Syntax Error: '{e.msg}'"
            if line:
                explained += " on line {e.lineno},"
            explained += " column {e.offset}"

        return explained

    @neovim.function("Speak")
    def fn_speak(self, text):
        self.speak(text)

    @neovim.command("SpeakLine")
    def cmd_speak_line(self):
        current = self.vim.current.line
        self.speak(current)

    @neovim.command("SpeakLineDetail")
    def cmd_speak_line_detail(self):
        current = self.vim.current.line
        self.speak(
            current,
            brackets=True,
            generic=False,
            speed=self.get_option(self.Options.SPEED) - 100,
        )

    @neovim.command("SpeakLineExplain")
    def cmd_speak_line_explain(self):
        current = self.vim.current.line.strip()

        explained = self.explain(current, line=False)

        self.speak(
            explained,
            stop=True,
            standard=False,
            brackets=False,
            indent_status=False,
            speed=200,
        )

    @neovim.command("SpeakRange", range=True)
    def cmd_speak_range(self, line_range):
        for i in self.get_current_selection():
            self.speak(i)

    @neovim.command("SpeakRangeDetail", range=True)
    def cmd_speak_range_detail(self, line_range):
        for i in self.get_current_selection():
            self.speak(
                i,
                brackets=True,
                generic=False,
                speed=self.get_option(self.Options.SPEED) - 100,
            )

    @neovim.command("SpeakRangeExplain", range=True)
    def cmd_explain_range(self, line_range):
        lines = self.get_current_selection()
        new_first_line = lines[0].lstrip()
        base_indent_level = len(lines[0]) - len(new_first_line)

        new_lines = [line[base_indent_level:] for line in lines]

        code = "\n".join(new_lines)

        explained = self.explain(code, line=True)

        self.speak(
            explained,
            stop=True,
            standard=False,
            brackets=False,
            indent_status=False,
            speed=200,
        )

    @neovim.autocmd("CursorMoved", eval=r"[getline('.'), getcursorcharpos()]")
    @neovim.autocmd("CursorMovedI", eval=r"[getline('.'), getcursorcharpos()]")
    @requires_option(Options.AUTO_SPEAK_LINE)
    def handle_cursor_moved(self, data):
        ignore = False
        if self.vim.api.get_var("ignorecursorevent"):
            ignore = True
            self.vim.api.set_var("ignorecursorevent", False)
        line, pos = data
        orow, ocol = self.cursor_pos
        oline = self.current_line
        _, row, col, *_ = pos
        self.cursor_pos = (row, col)
        self.current_line = line
        if ignore:
            return
        char = self.vim.funcs.strcharpart(line, col - 1, 1)
        if row == orow and line == oline:
            text = char
        else:
            text = line
        self.speak(text, stop=True)

    @neovim.autocmd(
        "TextYankPost", eval=r"[v:event.operator, v:event.regcontents]", sync=True
    )
    def handle_delete(self, data):
        self.vim.api.set_var("ignorecursorevent", True)
        operator, textlist = data
        if operator == "d":
            text = textlist[0]
            self.speak(text, stop=True)

    @neovim.autocmd("CmdlineEnter")
    @requires_option(Options.AUTO_SPEAK_OUTPUT)
    def record_output(self):
        var = self.outvar
        self.vim.command(f":redir => {var}")

    @neovim.autocmd("CmdlineLeave")
    @requires_option(Options.AUTO_SPEAK_OUTPUT)
    def speak_output(self):
        var = self.outvar
        self.vim.command(":redir END")
        text = self.vim.api.get_var(var)
        if text:
            text = text.replace("\0", "\n").strip()
            self.speak(text, stop=True)

    @neovim.autocmd("InsertEnter")
    @requires_option(Options.SPEAK_MODE_TRANSITIONS)
    def handle_insert_enter(self):
        self.speak("INSERT ON", stop=True)

    @neovim.autocmd("InsertLeave")
    @requires_option(Options.SPEAK_MODE_TRANSITIONS)
    def handle_insert_leave(self):
        self.speak("INSERT OFF", stop=True)

    @neovim.autocmd("InsertCharPre", eval='[v:char, getcursorcharpos(".")]')
    def handle_insert_char(self, data):
        speak_keypresses = self.get_option(self.Options.SPEAK_KEYPRESSES)
        speak_words = self.get_option(self.Options.SPEAK_WORDS)
        if not (speak_keypresses or speak_words):
            return
        char, position = data
        _, row, col, *_ = position
        line = self.vim.current.line
        last_word = None
        if speak_words and re.match(r"\W", char):
            if re.match(r"\w", line[col - 2]):
                pre_line = line[:col]
                pre_last_word = re.split(r"\W+", pre_line)
                pre_last_word = list(filter(lambda w: bool(w), pre_last_word))
                last_word = pre_last_word[-1]
        if last_word is not None and len(last_word) > 0:
            self.speak(last_word, stop=True)
        if speak_keypresses:
            self.speak(char, stop=False)

    @neovim.autocmd("CompleteDone", eval="v:completed_item")
    @requires_option(Options.SPEAK_COMPLETIONS)
    def handle_complete_done(self, item):
        if not item:
            return

        if isinstance(item, dict):
            item = item["word"]

        self.speak(item)
