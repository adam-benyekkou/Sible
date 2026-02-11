ace.define("ace/theme/catppuccin_mocha-css", ["require", "exports", "module"], function (require, exports, module) {
    module.exports = "\
.ace-catppuccin-mocha .ace_gutter {\
  background: #1e1e2e;\
  color: #6c7086;\
  border-right: 1px solid #313244;\
}\
.ace-catppuccin-mocha .ace_gutter-active-line {\
  background-color: #313244;\
}\
.ace-catppuccin-mocha .ace_print-margin {\
  width: 1px;\
  background: #313244;\
}\
.ace-catppuccin-mocha {\
  background-color: #1e1e2e;\
  color: #cdd6f4;\
}\
.ace-catppuccin-mocha .ace_cursor {\
  color: #f5e0dc;\
}\
.ace-catppuccin-mocha .ace_marker-layer .ace_selection {\
  background: #45475a;\
}\
.ace-catppuccin-mocha.ace_multiselect .ace_selection.ace_start {\
  box-shadow: 0 0 3px 0px #1e1e2e;\
}\
.ace-catppuccin-mocha .ace_marker-layer .ace_step {\
  background: #f9e2af;\
}\
.ace-catppuccin-mocha .ace_marker-layer .ace_bracket {\
  margin: -1px 0 0 -1px;\
  border: 1px solid #585b70;\
}\
.ace-catppuccin-mocha .ace_marker-layer .ace_active-line {\
  background: rgba(49, 50, 68, 0.6);\
}\
.ace-catppuccin-mocha .ace_gutter-cell {\
  padding-left: 8px;\
  padding-right: 6px;\
}\
.ace-catppuccin-mocha .ace_marker-layer .ace_selected-word {\
  border: 1px solid #45475a;\
}\
.ace-catppuccin-mocha .ace_invisible {\
  color: #585b70;\
}\
.ace-catppuccin-mocha .ace_keyword,\
.ace-catppuccin-mocha .ace_meta,\
.ace-catppuccin-mocha .ace_storage,\
.ace-catppuccin-mocha .ace_storage.ace_type {\
  color: #cba6f7;\
}\
.ace-catppuccin-mocha .ace_keyword.ace_operator {\
  color: #89dceb;\
}\
.ace-catppuccin-mocha .ace_constant.ace_character,\
.ace-catppuccin-mocha .ace_constant.ace_language,\
.ace-catppuccin-mocha .ace_constant.ace_numeric,\
.ace-catppuccin-mocha .ace_keyword.ace_other.ace_unit {\
  color: #fab387;\
}\
.ace-catppuccin-mocha .ace_constant.ace_other {\
  color: #f5e0dc;\
}\
.ace-catppuccin-mocha .ace_invalid {\
  color: #cdd6f4;\
  background-color: #f38ba8;\
}\
.ace-catppuccin-mocha .ace_invalid.ace_deprecated {\
  color: #cdd6f4;\
  background-color: #a6adc8;\
}\
.ace-catppuccin-mocha .ace_support.ace_function {\
  color: #89b4fa;\
}\
.ace-catppuccin-mocha .ace_support.ace_constant {\
  color: #fab387;\
}\
.ace-catppuccin-mocha .ace_support.ace_class,\
.ace-catppuccin-mocha .ace_support.ace_type {\
  color: #f9e2af;\
}\
.ace-catppuccin-mocha .ace_fold {\
  background-color: #89b4fa;\
  border-color: #cdd6f4;\
}\
.ace-catppuccin-mocha .ace_entity.ace_name.ace_function,\
.ace-catppuccin-mocha .ace_entity.ace_other,\
.ace-catppuccin-mocha .ace_entity.ace_other.ace_attribute-name,\
.ace-catppuccin-mocha .ace_variable {\
  color: #89b4fa;\
}\
.ace-catppuccin-mocha .ace_variable.ace_parameter {\
  color: #f5c2e7;\
  font-style: italic;\
}\
.ace-catppuccin-mocha .ace_string {\
  color: #a6e3a1;\
}\
.ace-catppuccin-mocha .ace_string.ace_regexp {\
  color: #f5c2e7;\
}\
.ace-catppuccin-mocha .ace_comment {\
  color: #6c7086;\
  font-style: italic;\
}\
.ace-catppuccin-mocha .ace_heading,\
.ace-catppuccin-mocha .ace_markup.ace_heading {\
  color: #f38ba8;\
}\
.ace-catppuccin-mocha .ace_entity.ace_name.ace_tag,\
.ace-catppuccin-mocha .ace_meta.ace_tag {\
  color: #f38ba8;\
}\
.ace-catppuccin-mocha .ace_indent-guide {\
  background: url(data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAACCAYAAACZgbYnAAAAEklEQVQImWNgYGBgYHB3d/8PAAOIAdULw8qMAAAAAElFTkSuQmCC) right repeat-y;\
}\
.ace-catppuccin-mocha .ace_indent-guide-active {\
  background: url(data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAACCAYAAACZgbYnAAAAEklEQVQImWOQkpL6DwAClAFVNxb1OAAAAABJRU5ErkJggg==) right repeat-y;\
}\
";
});

ace.define("ace/theme/catppuccin_mocha", ["require", "exports", "module", "ace/theme/catppuccin_mocha-css", "ace/lib/dom"], function (require, exports, module) {
    exports.isDark = true;
    exports.cssClass = "ace-catppuccin-mocha";
    exports.cssText = require("./catppuccin_mocha-css");

    var dom = require("../lib/dom");
    dom.importCssString(exports.cssText, exports.cssClass, false);
});

(function () {
    ace.require(["ace/theme/catppuccin_mocha"], function (m) {
        if (typeof module == "object" && typeof exports == "object" && module) {
            module.exports = m;
        }
    });
})();
