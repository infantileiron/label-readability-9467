import { formError, icon, seal } from '../components/common/ui.js';

export function loginPage() {
  return `<main class="login">
    <div class="login-main">
      <div class="brand">${seal()}<span><b>平渡展陈</b><small>展陈设计与观众研究组</small></span></div>
      <section class="login-form"><p class="eyebrow">印前复验工作台</p><h1>易读展签<br>复验。</h1>
      <p class="lede">登录后查看展签校样、登记观众测读，并完成付印前的会签。</p>
      <form id="login-form">
        <label>账号<input name="username" autocomplete="username" required placeholder="输入账号"></label>
        <label>密码<input name="password" type="password" autocomplete="current-password" required placeholder="输入密码"></label>
        ${formError}<button class="primary login-submit" type="submit">进入工作台 ${icon('arrow')}</button>
      </form>
      <div class="login-demos" aria-label="填入演示账号"><span>演示登录</span><button type="button" data-demo="analyst">分析员</button><button type="button" data-demo="curator">展陈主管</button><button type="button" data-demo="viewer">观察员</button></div></section>
    </div>
    <aside class="login-art" aria-label="青釉刻划纹执壶展签示意">
      <div class="art-heading"><span>平渡 · 常设展二厅</span><span>展签校样</span></div>
      <div class="art-wall"><div class="art-sheet">
        <span class="art-code">馆藏说明 / YA-02</span><div class="art-line"></div><p class="art-title">青釉刻划纹执壶</p>
        <p>工匠先在未烧的壶身上刻出花纹，<br>再涂釉，把壶放进窑里烧。</p>
        <span class="art-caption">看一看花纹凹进去的地方。</span>
      </div></div>
      <div class="art-footer"><span>易读样张</span><span>青釉器组 · 北宋</span></div>
    </aside>
  </main>`;
}
