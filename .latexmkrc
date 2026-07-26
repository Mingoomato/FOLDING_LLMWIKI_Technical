# latexmk configuration for LLMWiki (lualatex + glossaries + makeindex + bibtex)
$pdf_mode = 4;            # lualatex
$lualatex = 'lualatex -interaction=nonstopmode -halt-on-error -file-line-error -synctex=1 %O %S';
$bibtex_use = 2;         # run bibtex when needed
$out_dir = 'build';

# glossaries / acronyms support
add_cus_dep('glo', 'gls', 0, 'run_makeglossaries');
add_cus_dep('acn', 'acr', 0, 'run_makeglossaries');
sub run_makeglossaries {
    my ($base_name, $path) = fileparse($_[0]);
    my $dir = $path ? "-d $path" : '';
    system("makeglossaries $dir $base_name");
}

# clean up glossary/index aux files too
push @generated_exts, 'glo', 'gls', 'glg', 'acn', 'acr', 'alg', 'ist', 'xdy';
push @generated_exts, 'idx', 'ind', 'ilg';
