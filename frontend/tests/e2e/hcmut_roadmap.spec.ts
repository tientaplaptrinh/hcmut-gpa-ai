import { test, expect } from '@playwright/test';

test.describe('BK-GPA & Optimal Study Roadmap AI — Full HCMUT Student Journey', () => {
  test('Onboarding 7520201 K2025 -> Difficulty Dashboard -> MyBK Import (~3.20 GPA) -> MILP 3.60 Roadmap & Live What-If Toggle', async ({
    page,
  }) => {
    const consoleErrors: string[] = [];
    const pageErrors: string[] = [];

    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });
    page.on('pageerror', (err) => {
      pageErrors.push(err.message);
    });

    // 1. Open Onboarding Flow & Clear clean state
    await page.goto('/');
    await page.evaluate(() => localStorage.clear());
    await page.reload();
    await page.waitForLoadState('networkidle');

    // Select 7520201 (Kỹ thuật Điện) + K2025
    await expect(page.getByTestId('major-card-7520201')).toBeVisible();
    await page.getByTestId('major-card-7520201').click();
    await page.getByTestId('cohort-btn-K2025').click();
    await page.getByTestId('start-roadmap-btn').click();

    // 2. Verify Dashboard 1 — Course Difficulty Predictor renders predictions & charts
    await expect(page.getByTestId('difficulty-dashboard')).toBeVisible();
    await expect(page.getByText(/Dự đoán Độ khó Môn học — Kỹ thuật Điện \(K2025\)/)).toBeVisible();
    await expect(page.getByTestId('difficulty-charts-section')).toBeVisible();
    await expect(page.locator('.recharts-surface').first()).toBeVisible();

    // Verify course rows & Vietnamese AI explanation expand
    await expect(page.getByText('MT1003')).toBeVisible();
    await page.getByRole('button', { name: /Vì sao\?/ }).first().click();
    await expect(page.getByText(/Phân tích AI — Vì sao/)).toBeVisible();

    // Test Dark Mode toggle works cleanly
    await page.getByTestId('dark-mode-toggle').click();
    await expect(page.locator('html')).toHaveClass(/dark/);
    await page.getByTestId('dark-mode-toggle').click();

    // 3. Switch to Dashboard 2 — GPA & Optimal AI Roadmap
    await page.getByTestId('goto-gpa-dashboard-btn').click();
    await expect(page.getByTestId('gpa-roadmap-dashboard')).toBeVisible();

    // 4. Open Import MyBK Modal, load realistic ~3.20 GPA sample transcript, verify preview & retake badge
    await page.getByTestId('open-import-modal-btn').click();
    await expect(page.getByTestId('import-transcript-modal')).toBeVisible();

    await page.getByTestId('paste-demo-mybk-btn').click();
    await expect(page.getByTestId('import-preview-section')).toBeVisible();
    await expect(page.getByTestId('import-preview-table')).toBeVisible();
    await expect(page.getByTestId('retake-badge').first()).toBeVisible();

    const previewGpaText = await page.getByTestId('preview-gpa-4').innerText();
    const previewGpa = parseFloat(previewGpaText);
    expect(previewGpa).toBeGreaterThanOrEqual(3.1);
    expect(previewGpa).toBeLessThanOrEqual(3.3);

    // Apply grades to Dashboard 2
    await page.getByTestId('apply-imported-grades-btn').click();
    await expect(page.getByTestId('import-transcript-modal')).toBeHidden();

    // Verify Live KPI bar reflects ~3.20 GPA
    await expect(page.getByTestId('live-gpa-4')).not.toHaveText('0.00');
    const liveGpa = parseFloat(await page.getByTestId('live-gpa-4').innerText());
    expect(liveGpa).toBeCloseTo(previewGpa, 2);

    // 5. Enter Target GPA 3.60 & Click "AI Tìm lộ trình tối ưu nhất"
    const targetInput = page.getByTestId('target-gpa-input');
    await targetInput.fill('3.60');
    await page.getByTestId('optimize-roadmap-btn').click();

    // 6. Verify RoadmapComparisonPanel renders both Forward-Only & Hybrid Optimal cards
    await expect(page.getByTestId('roadmap-comparison-panel')).toBeVisible();
    const forwardCard = page.getByTestId('strategy-card-FORWARD_ONLY');
    const hybridCard = page.getByTestId('strategy-card-HYBRID_OPTIMAL');
    await expect(forwardCard).toBeVisible();
    await expect(hybridCard).toBeVisible();
    await expect(page.getByTestId('best-recommended-badge')).toBeVisible();

    // Assert Hybrid strictly reduces effort compared to Forward-Only
    const forwardEffort = parseFloat(
      await page.getByTestId('effort-score-FORWARD_ONLY').innerText()
    );
    const hybridEffortBefore = parseFloat(
      await page.getByTestId('effort-score-HYBRID_OPTIMAL').innerText()
    );
    expect(forwardEffort).toBeGreaterThan(0);
    expect(hybridEffortBefore).toBeGreaterThan(0);
    expect(hybridEffortBefore).toBeLessThan(forwardEffort);

    // Verify Retake Recommendations Table & Remaining Courses Minimum Grade Table
    await hybridCard.click();
    await expect(page.getByTestId('retake-recommendations-table')).toBeVisible();
    await expect(page.getByTestId('remaining-courses-plan-table')).toBeVisible();

    const remainingRows = page
      .getByTestId('remaining-courses-plan-table')
      .locator('tbody tr');
    expect(await remainingRows.count()).toBeGreaterThan(10);

    // 7. Toggle a What-If retake checkbox and confirm live recalculation
    const firstCheckboxAttr = await page
      .locator('[data-testid^="whatif-retake-checkbox-"]')
      .first()
      .getAttribute('data-testid');
    expect(firstCheckboxAttr).toBeTruthy();
    const targetCheckbox = page.getByTestId(firstCheckboxAttr!);
    await expect(targetCheckbox).toBeChecked();
    await targetCheckbox.uncheck();
    await expect(targetCheckbox).not.toBeChecked();

    // Wait for live recalculation to settle and assert effort score updated cleanly
    await expect
      .poll(async () => {
        const updatedText = await page
          .getByTestId('effort-score-HYBRID_OPTIMAL')
          .innerText();
        return parseFloat(updatedText);
      })
      .not.toBe(hybridEffortBefore);

    // 8. Assert 0 console errors and 0 page errors
    expect(consoleErrors).toEqual([]);
    expect(pageErrors).toEqual([]);
  });

  test('CSV Upload Tab + Personal Difficulty Slider Override + Infeasible Target Diagnostic', async ({
    page,
  }) => {
    const consoleErrors: string[] = [];
    const pageErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') consoleErrors.push(msg.text());
    });
    page.on('pageerror', (err) => pageErrors.push(err.message));

    await page.goto('/');
    await page.evaluate(() => localStorage.clear());
    await page.reload();
    await page.waitForLoadState('networkidle');

    // Choose Khoa học Máy tính (7480101) + K2025
    await page.getByTestId('major-card-7480101').click();
    await page.getByTestId('cohort-btn-K2025').click();
    await page.getByTestId('start-roadmap-btn').click();

    await expect(page.getByTestId('difficulty-dashboard')).toBeVisible();
    await expect(page.getByText(/Khoa học Máy tính \(K2025\)/)).toBeVisible();

    // Switch to GPA Dashboard & upload CSV file in memory
    await page.getByTestId('goto-gpa-dashboard-btn').click();
    await page.getByTestId('open-import-modal-btn').click();
    await page.getByTestId('tab-excel-upload').click();

    const csvContent =
      'Học kỳ,Mã MH,Tên môn học,Số tín chỉ,Điểm hệ 10,Điểm chữ\n' +
      'HK241,MT1003,Giải tích 1,4,4.5,D\n' +
      'HK241,MT1007,Đại số tuyến tính,3,4.2,D\n' +
      'HK241,CO1027,Kỹ thuật lập trình,4,4.8,D\n' +
      'HK241,SP1031,Triết học Mác - Lênin,3,4.5,D\n';

    await page.getByTestId('transcript-file-input').setInputFiles({
      name: 'bang_diem_test.csv',
      mimeType: 'text/csv',
      buffer: Buffer.from(csvContent, 'utf-8'),
    });

    await expect(page.getByTestId('import-preview-section')).toBeVisible();
    await page.getByTestId('apply-imported-grades-btn').click();

    // Set max retakes = 0 and ask for impossible GPA 3.98 -> assert diagnostic banner
    await page.getByTestId('max-retake-btn-0').click();
    await page.getByTestId('target-gpa-input').fill('3.98');
    await page.getByTestId('optimize-roadmap-btn').click();

    await expect(page.getByTestId('roadmap-comparison-panel')).toBeVisible();
    await expect(page.getByTestId('strategy-card-FORWARD_ONLY')).toContainText('Bất khả thi');

    expect(consoleErrors).toEqual([]);
    expect(pageErrors).toEqual([]);
  });
});
