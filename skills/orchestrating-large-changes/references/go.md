# Go idioms for the method

| Method term | In Go |
|---|---|
| Contract skeleton | Interfaces and types in the owning package, bodies `panic("not implemented: T7")`, a doc-comment line per rule the type cannot say |
| Implementation check | `var _ Store = (*sqlStore)(nil)` beside each planned implementation |
| Consumer check | A `_test.go` in the consumer package that calls the producer's API the way the consumer will; a mismatch fails `go vet ./...` |
| Fake | A `<pkg>test` package (`storetest.NewFake()`), compile-checked against the interface |
| Conformance suite | `storetest.Run(t, func() store.Store)`, in the style of `testing/fstest.TestFS`; every implementation and the fake call it |
| Wire fixture | `testdata/*.golden` read by a table or `Example` test, rewritten with `-update`; a client in another language reads the same file |
| Test stub | `func TestRemoveRefusesDirtyWorktree(t *testing.T) { t.Skip("T7 R1") }` |
| Stub count | `go test ./... -v 2>&1 \| grep -c ': T7 '` is 0 before merge |
| Carried finding | `t.Skip("carried from T6 review: lost update on concurrent Save")` in the owning package |
| Contract reading | `go doc -all ./internal/store` |
| API-diff check | `apidiff` (`golang.org/x/exp/cmd/apidiff`): `apidiff -w base.api <pkg>` on the skeleton commit, `apidiff base.api <pkg>` on the branch; or a `go/types` test that writes exported signatures to a golden file |
| Registration point | `func init() { routes.Register("remove", newRemove) }` in the task's own file; `main` imports the package for side effects |
| Lane check | `go build ./... && go vet ./...`, then `go test -race` on the touched packages and their importers |
| Flake hunt | `go test -race -count=20 ./<pkg>`, several packages at once |
