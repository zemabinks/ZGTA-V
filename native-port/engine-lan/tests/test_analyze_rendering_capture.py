import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / 'analyze_rendering_capture.py'
SPEC = importlib.util.spec_from_file_location('render_capture_analyzer', SCRIPT)
analyzer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analyzer)


def fixture():
    row = dict(vs='0000000000000001', ps='c6a7f1c7e84ba9eb', drawKind='1', vertexBuffer='9',
               drawArg1='3174', drawArg2='1', target='12', depth='13', frame='60', snapshotFrame='60',
               version='100', stipple='30', constantBuffer='156', first='0', num='0', metalIndex='2',
               encoded='1', boundValid='1', shadowValid='1', outcome='ok')
    for i in range(4):
        row['shadow' + str(i)] = row['bound' + str(i)] = '3f800000'
    return dict(format='zgta-performance-v2', renderingDiagnostics=dict(
        format='zgta-rendering-consumer105-v1', counters=dict(generation=1, observedDraws=1000,
        constantBufferCopies=0, shadowCopiesUpdated=0, unknownSourceCopies=0), observations=[row]),
        context=dict(deviceModel='iPhone16,1', build='v2.0 (105)', host='ws://private.invalid:47541',
                     room='PRIVATE_ROOM', playerName='PRIVATE_PLAYER'),
        conditions=dict(thermalState=dict(first=1, last=2, minimum=1, maximum=2, counterReset=False)),
        timeline=[dict(elapsedMS=0, conditions=dict(thermalState=1, requestedFrameInterval=1)),
                  dict(elapsedMS=1000, conditions=dict(thermalState=2, requestedFrameInterval=2))],
        averageFPS=35.1, durationMS=30000)


class RenderingCaptureAnalysisTests(unittest.TestCase):
    def test_masks_are_facts_and_different_targets_have_distinct_signatures(self):
        data = fixture()
        other = copy.deepcopy(data['renderingDiagnostics']['observations'][0])
        other['target'] = '14'
        other['frame'] = other['snapshotFrame'] = '120'
        other['bound0'] = '00000000'
        data['renderingDiagnostics']['observations'].append(other)
        result = analyzer.analyze(data, 'a' * 64, 123)
        self.assertEqual(result['observations']['drawSignatureCount'], 2)
        self.assertEqual(result['observations']['matchingShadowAndBoundRecords'], 1)
        self.assertEqual(result['observations']['mismatchingShadowAndBoundRecords'], 1)
        masks = result['drawSignatures'][0]['masks'][0]
        self.assertEqual(masks['stippleCode'], 30)
        self.assertEqual(masks['boundWords'], ['3f800000'] * 4)
        self.assertNotIn('bug', masks)
        self.assertEqual(result['performance']['observedTransitions'][1]['observedValues'],
                         dict(thermalState=2, requestedFrameInterval=2))
        self.assertTrue(result['performance']['diagnosticNotCleanBenchmark'])
        self.assertNotIn('PRIVATE_ROOM', json.dumps(result))
        self.assertNotIn('PRIVATE_PLAYER', json.dumps(result))
        self.assertNotIn('private.invalid', json.dumps(result))

    def test_rejects_malformed_schema_words_numbers_and_bounds(self):
        cases = []
        bad = fixture(); bad['renderingDiagnostics']['format'] = 'unknown'; cases.append(bad)
        bad = fixture(); bad['renderingDiagnostics']['observations'] *= 257; cases.append(bad)
        bad = fixture(); bad['renderingDiagnostics']['observations'][0]['bound0'] = 'bad'; cases.append(bad)
        bad = fixture(); bad['renderingDiagnostics']['observations'][0]['frame'] = '-1'; cases.append(bad)
        bad = fixture(); bad['renderingDiagnostics']['observations'][0]['stipple'] = '32'; cases.append(bad)
        bad = fixture(); bad['renderingDiagnostics']['counters']['observedDraws'] = True; cases.append(bad)
        bad = fixture(); bad['averageFPS'] = float('nan'); cases.append(bad)
        for case in cases:
            with self.subTest(case=cases.index(case)), self.assertRaises(ValueError):
                analyzer.analyze(case, 'b' * 64, 123)

    def test_cli_explicit_output_and_source_preservation(self):
        with tempfile.TemporaryDirectory(prefix='zgta-capture-analysis-') as temporary:
            root = Path(temporary)
            source, output = root / 'report.txt', root / 'summary.json'
            raw = json.dumps(fixture()).encode()
            source.write_bytes(raw)
            result = subprocess.run([sys.executable, '-B', str(SCRIPT), str(source), '--output', str(output)],
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(output.read_text())
            self.assertEqual(summary['source']['bytes'], len(raw))
            self.assertEqual(source.read_bytes(), raw)
            self.assertEqual(set(root.iterdir()), {source, output})
            rejected = subprocess.run([sys.executable, '-B', str(SCRIPT), str(output), '--output', str(output)],
                                      text=True, capture_output=True)
            self.assertEqual(rejected.returncode, 2)
            self.assertEqual(json.loads(output.read_text()), summary)


if __name__ == '__main__':
    unittest.main()
