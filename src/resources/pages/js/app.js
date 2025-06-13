// 初始化 WebChannel
document.addEventListener("DOMContentLoaded", function() {
  if (typeof qt !== 'undefined') {
    new QWebChannel(qt.webChannelTransport, function(channel) {
      window.pyBridge = channel.objects.pyBridge;
      
      // 测试连接
      pyBridge.ping(function(response) {
        console.log("后台连接测试:", response);
      });
      
      // 获取游戏列表
      updateGamesList();
    });
  }
});

// 更新游戏列表函数
async function updateGamesList() {
  try {
    const games = await new Promise(resolve => pyBridge.getGamesList(resolve));
    renderGames(JSON.parse(games));
  } catch (error) {
    console.error("获取游戏列表失败:", error);
  }
}

// 渲染游戏卡片
function renderGames(games) {
  const container = document.querySelector('.games-grid');
  container.innerHTML = ''; // 清空现有内容
  
  games.forEach(game => {
    const card = `
      <div class="game-card" data-id="${game.id}">
        <div class="game-banner" style="${getBannerStyle(game)}">
          <div class="game-icon" style="${getIconStyle(game)}">
            <i class="${getGameIcon(game)}"></i>
          </div>
        </div>
        <div class="game-info">
          <div class="game-title">${game.version}${game.loader_type !== 'vanilla' ? ` (${game.loader_type})` : ''}</div>
          <div class="game-meta">
            <span>玩家: ${game.player_name}</span>
            <span class="game-status">${getStatusText(game)}</span>
          </div>
          <div class="game-actions">
            <button class="play-btn" onclick="launchGame('${game.id}')">
              ${game.status === 'downloading' ? '<i class="fas fa-spinner fa-spin"></i> 下载中' : '启动游戏'}
            </button>
            <button class="settings-btn" onclick="cancelDownload('${game.id}')">
              <i class="fas fa-times"></i>
            </button>
          </div>
          ${game.status === 'downloading' ? `
          <div class="progress-bar">
            <div class="progress" style="width: ${game.progress}%"></div>
          </div>` : ''}
        </div>
      </div>
    `;
    container.insertAdjacentHTML('beforeend', card);
  });
}

// 启动游戏函数
function launchGame(gameId) {
  pyBridge.launchGame(gameId, function(success) {
    if (success) {
      console.log(`游戏 ${gameId} 启动成功`);
    } else {
      alert(`启动游戏失败: ${gameId}`);
    }
  });
}

// 取消下载函数
function cancelDownload(gameId) {
  pyBridge.cancelDownload(gameId, function(success) {
    if (success) {
      console.log(`下载已取消: ${gameId}`);
      updateGamesList();
    }
  });
}

// 添加新游戏函数
function addNewGame() {
  const version = prompt("输入Minecraft版本 (例如 1.20.1):");
  const player = prompt("输入玩家名称:");
  
  if (version && player) {
    pyBridge.downloadGame(version, player, "vanilla", function(success) {
      if (success) {
        updateGamesList();
      } else {
        alert("下载失败，请查看日志");
      }
    });
  }
}

// 辅助函数
function getBannerStyle(game) {
  const colors = {
    'vanilla': ['#4CAF50', '#2E7D32'],
    'fabric': ['#2196F3', '#0D47A1'],
    'forge': ['#F44336', '#B71C1C']
  };
  const [color1, color2] = colors[game.loader_type] || colors.vanilla;
  return `background: linear-gradient(45deg, ${color1}, ${color2});`;
}

function getStatusText(game) {
  const statusMap = {
    'downloading': '下载中',
    'installed': '已安装',
    'cancelled': '已取消'
  };
  return statusMap[game.status] || '就绪';
}