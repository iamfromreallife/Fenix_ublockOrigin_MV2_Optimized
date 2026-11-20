"""No-network correctness checks for release selection and three-way rebasing."""
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import sync_upstream as sync

class SyncEngineTests(unittest.TestCase):
    def test_preserves_independent_custom_file(self):
        ours={'upstream.js':b'a\n','custom.js':b'custom\n'}
        result,counts,conflicts=sync.merge_files({'upstream.js':b'a\n'},ours,{'upstream.js':b'b\n'})
        self.assertFalse(conflicts)
        self.assertEqual(result,{'upstream.js':b'b\n','custom.js':b'custom\n'})

    def test_keeps_custom_change_when_upstream_unchanged(self):
        result,counts,conflicts=sync.merge_files({'a':b'a'}, {'a':b'fenix'}, {'a':b'a'})
        self.assertEqual(result['a'],b'fenix')
        self.assertFalse(conflicts)

    def test_merges_non_overlapping_changes(self):
        base=b'first\nsecond\nthird\nfourth\nfifth\nsixth\nseventh\neighth\nninth\n'
        local=base.replace(b'first',b'fenix')
        upstream=base.replace(b'ninth',b'official')
        result,counts,conflicts=sync.merge_files({'a':base},{'a':local},{'a':upstream})
        self.assertFalse(conflicts)
        self.assertEqual(result['a'],base.replace(b'first',b'fenix').replace(b'ninth',b'official'))
        self.assertEqual(counts['merged'],1)

    def test_fails_closed_on_overlapping_changes(self):
        _,_,conflicts=sync.merge_files({'a':b'a\n'}, {'a':b'fenix\n'}, {'a':b'upstream\n'})
        self.assertEqual([x['path'] for x in conflicts],['a'])

    def test_fails_closed_on_binary_conflicts(self):
        _,_,conflicts=sync.merge_files({'a':b'\0a'},{'a':b'\0local'},{'a':b'\0remote'})
        self.assertEqual(len(conflicts),1)

    def test_removes_unmodified_upstream_deleted_file(self):
        result,_,conflicts=sync.merge_files({'a':b'a'},{'a':b'a'}, {})
        self.assertNotIn('a',result)
        self.assertFalse(conflicts)

    def test_preserves_local_deleted_file(self):
        result,_,conflicts=sync.merge_files({'a':b'a'}, {}, {'a':b'a'})
        self.assertNotIn('a',result)
        self.assertFalse(conflicts)

    def test_detects_add_add_collision(self):
        _,_,conflicts=sync.merge_files({}, {'a':b'local'}, {'a':b'upstream'})
        self.assertEqual(len(conflicts),1)

    def test_release_list_stops_at_cursor(self):
        calls=[]
        def fake(url):
            calls.append(url)
            if url.endswith('page=1'):
                return [{'tag_name':str(i)} for i in range(100)]
            if url.endswith('page=2'):
                return [{'tag_name':'1.76.5b6'}]+[{'tag_name':str(i)} for i in range(99)]
            self.fail('Unexpected extra page')
        with patch.object(sync, 'get_json', fake):
            items=sync.release_list({'upstream_tag':'1.76.5b6'})
        self.assertEqual(len(items),200)
        self.assertEqual(len(calls),2)

    def test_release_selection_includes_stable_and_beta(self):
        baseline={'upstream_tag':'1.76.5b6','published_at':'2026-11-19T18:22:10Z','release_id':10}
        releases=[
            {'tag_name':'1.76.6b0','published_at':'2026-11-20T17:00:00Z','id':12,'draft':False,'assets':[{'name':'uBlock0_1.76.6b0.chromium.zip'}],'prerelease':True},
            {'tag_name':'1.76.6','published_at':'2026-11-20T16:00:00Z','id':11,'draft':False,'assets':[{'name':'uBlock0_1.76.6.chromium.zip'}],'prerelease':False},
        ]
        self.assertEqual(sync.next_release(releases,baseline)['tag_name'],'1.76.6')
        baseline.update(published_at='2026-11-20T16:00:00Z', release_id=11)
        self.assertEqual(sync.next_release(releases,baseline)['tag_name'],'1.76.6b0')

if __name__=='__main__': unittest.main(verbosity=2)
