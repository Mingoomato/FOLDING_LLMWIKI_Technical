++ # LLMWiki Makefile - Build system for LaTeX documentation
++ 
++ # Main target
++ PDF = LLMWiki.pdf
++ 
++ # LaTeX settings
++ LATEX = latexmk
++ LATEX_FLAGS = -pdf -interaction=nonstopmode -halt-on-error -file-line-error -synctex=1
++ LATEX_CLEAN = -c
++ 
++ # Source files
++ MAIN = LLMWiki.tex
++ 
++ # Directories
++ BUILD_DIR = build
++ BIB_DIR = bibliography
++ 
++ .PHONY: all clean pdf bib view help
++ 
++ all: pdf
++ 
++ pdf: $(BUILD_DIR)/$(PDF)
++ 
++ $(BUILD_DIR)/$(PDF): $(MAIN) *.tex acronyms.tex glossary.tex bibliography/LLMWiki.bib docs/*/*.tex appendix/*.tex
++ 	@mkdir -p $(BUILD_DIR)
++ 	$(LATEX) $(LATEX_FLAGS) -output-directory=$(BUILD_DIR) $(MAIN)
++ 	@cp $(BUILD_DIR)/$(PDF) .
++ 
++ bib: $(BUILD_DIR)/$(MAIN:.tex=.bbl)
++ 
++ $(BUILD_DIR)/$(MAIN:.tex=.bbl): bibliography/LLMWiki.bib $(MAIN)
++ 	@mkdir -p $(BUILD_DIR)
++ 	$(LATEX) $(LATEX_FLAGS) -output-directory=$(BUILD_DIR) -bibtex $(MAIN)
++ 
++ clean:
++ 	$(LATEX) $(LATEX_CLEAN) -output-directory=$(BUILD_DIR) $(MAIN)
++ 	rm -f $(PDF)
++ 	rm -rf $(BUILD_DIR)
++ 
++ view: pdf
++ 	@if command -v xdg-open > /dev/null; then xdg-open $(PDF); \
++ 	elif command -v open > /dev/null; then open $(PDF); \
++ 	elif command -v start > /dev/null; then start $(PDF); \
++ 	else echo "PDF built at $(PDF)"; fi
++ 
++ help:
++ 	@echo "LLMWiki Makefile Targets:"
++ 	@echo "  make pdf   - Build the PDF (default)"
++ 	@echo "  make bib   - Build bibliography only"
++ 	@echo "  make clean - Clean build artifacts"
++ 	@echo "  make view  - Build and open PDF"
++ 	@echo "  make help  - Show this help"
