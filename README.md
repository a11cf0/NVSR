# nvsr

Nvsr is a screen reader for Neovim, cross-platform console text editor.
Nvsr is a fully refactored and improved fork of [Neoreader](https://github.com/MaxwellBo/neoreader).

## Features

* Reads characters, words and lines when you navigate them;
* Reads characters and words as you type;
* Announces when you enter and leave insert mode;
* Reads output of NeoVim's commands (with some limitations);
* On Microsoft Windows uses either SAPI5 or your preffered screen reader;
* On Linux uses speech-dispatcher;
* On MacOS uses VoiceOver (we have plans to adopt it for usage without VoiceOver).

## Requirements

Nvsr requires [Neovim](https://github.com/neovim/neovim) with `if_python3`.
If `:echo has("python3")` returns `1`, then you're fine; otherwise, see below.

You can enable the Python 3 interface with `pip`:

    `pip install neovim`

You must be using Python 3.6 or newer.

## Installation

For [vim-plug](https://github.com/junegunn/vim-plug), add 

```vim
Plug 'MaxwellBo/neoreader'
```

to your configuration, and execute `:PlugInstall`.

Execute `:UpdateRemotePlugins` and restart Neovim.

## Configuration

```vim
" Original Neoreader configurations are present. They are not refactored and may be changed or deleted in future
nnoremap <Leader>q :SpeakLine<cr>
nnoremap <Leader>w :SpeakLineDetail<cr>
nnoremap <Leader>e :SpeakLineExplain<cr>
vnoremap <Leader>a :SpeakRange<cr>
vnoremap <Leader>s :SpeakRangeDetail<cr>
vnoremap <Leader>d :SpeakRangeExplain<cr>

" defaults
let g:enable_at_startup = 1
let g:interpet_generic_infix = 1
let g:speak_brackets = 0
let g:speak_keypresses = 1
let g:speak_words = 1
let g:speak_mode_transitions = 0
let g:speak_completions = 0
let g:auto_speak_line = 1
let g:speak_indent = 0
let g:auto_speak_output = 1
let g:pitch_multiplier = 1
let g:speak_speed = 350
let g:use_espeak = 0
let g:use_ao2 = 1
let g:speak_voice = ''
```

## Contributors

- [Vladislav Kopylov](https://github.com/a11cf0);
- [Kirill Belousov](https://github.com/cyrmax).

### Contributors of original Neoreader project

- [Lewis Bobbermen](https://github.com/lewisjb)
- [Max Bo](https://github.com/MaxwellBo)
