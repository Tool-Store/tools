async ({ command, args }) => {
  // Reads the data an Instagram profile page already carries in its JSON blocks, so nothing beyond the
  // page view is requested. Field mapping follows OpenCLI's clis/instagram (see third_party/NOTICE).

  function failure(message, code) {
    const error = new Error(message);
    error.code = code;
    return error;
  }

  function checkPage() {
    if (/\bnot-logged-in\b/.test(document.documentElement.className)) {
      throw failure('Instagram showed the page as logged out', 'AUTH_REQUIRED');
    }
    if (/Please wait a few minutes before you try again/i.test(document.body?.innerText || '')) {
      throw failure('Instagram asked to wait before trying again', 'RATE_LIMITED');
    }
  }

  function pageData() {
    const blocks = [];
    for (const script of document.querySelectorAll('script[type="application/json"]')) {
      try { blocks.push(JSON.parse(script.textContent)); } catch { /* not every block is JSON data */ }
    }
    return blocks;
  }

  // The data sits deep inside Instagram's own loader structures, so it is found by shape, not by path.
  function find(blocks, test) {
    const stack = [...blocks];
    while (stack.length) {
      const node = stack.pop();
      if (!node || typeof node !== 'object') continue;
      if (!Array.isArray(node) && test(node)) return node;
      for (const value of Object.values(node)) {
        if (value && typeof value === 'object') stack.push(value);
      }
    }
    return null;
  }

  // "268M Followers, 196 Following, 32K Posts - See Instagram photos and videos from ..."
  function summaryCounts() {
    const summary = document.querySelector('meta[property="og:description"]')?.content || '';
    const match = summary.match(/([\d.,]+[KMB]?) Followers, ([\d.,]+[KMB]?) Following, ([\d.,]+[KMB]?) Posts/i);
    return match ? { followers: match[1], following: match[2], posts: match[3] } : null;
  }

  function profilePicture(user) {
    const candidates = [user.profile_pic_url_hd, user.hd_profile_pic_url_info?.url, user.profile_pic_url];
    return candidates.find((value) => typeof value === 'string' && value.startsWith('https://')) || '';
  }

  function toProfile(user) {
    return {
      username: user.username,
      name: typeof user.full_name === 'string' ? user.full_name : '',
      verified: Boolean(user.is_verified),
      private: Boolean(user.is_private),
      url: 'https://www.instagram.com/' + user.username + '/',
      bio: typeof user.biography === 'string' ? user.biography : '',
      followers: user.follower_count ?? user.edge_followed_by?.count ?? 0,
      following: user.following_count ?? user.edge_follow?.count ?? 0,
      posts: user.media_count ?? user.edge_owner_to_timeline_media?.count ?? 0,
      business: Boolean(user.is_business ?? user.is_business_account),
      category: user.category || user.category_name || '',
      website: user.external_url || '',
      // Signed CDN link: it expires, so download it rather than link to it.
      avatar_url: profilePicture(user),
    };
  }

  function toPost(media) {
    return {
      user: media?.user?.username || '',
      caption: media?.caption?.text || '',
      // Reels report engagement as plays rather than likes.
      likes: media?.like_count ?? media?.play_count ?? 0,
      comments: media?.comment_count ?? 0,
      type: media?.media_type === 1 ? 'photo' : media?.media_type === 2 ? 'video' : 'carousel',
      posted_at: media?.taken_at ? new Date(media.taken_at * 1000).toISOString() : '',
      url: media?.code ? 'https://www.instagram.com/p/' + media.code + '/' : '',
    };
  }

  function requireAccount() {
    if (!summaryCounts()) throw failure('Instagram profile page has no account data', 'NOT_FOUND');
  }

  const commands = {
    profile({ username }) {
      checkPage();
      const blocks = pageData();
      const wanted = username.toLowerCase();
      const user = find(blocks, (node) => typeof node.username === 'string' && node.username.toLowerCase() === wanted && 'follower_count' in node);
      if (user) return [toProfile(user)];
      requireAccount();
      return [{
        username,
        url: 'https://www.instagram.com/' + username + '/',
        ...summaryCounts(),
        note: 'Instagram showed only its page summary, so only these counts are available.',
      }];
    },

    posts({ limit }) {
      checkPage();
      const blocks = pageData();
      const holder = find(blocks, (node) => 'xdt_api__v1__feed__user_timeline_graphql_connection' in node);
      const edges = holder?.xdt_api__v1__feed__user_timeline_graphql_connection?.edges;
      if (!Array.isArray(edges)) {
        requireAccount();
        throw new Error('Instagram profile page carried no posts data');
      }
      return edges.map((edge) => edge?.node).filter(Boolean).slice(0, limit).map(toPost);
    },
  };

  try {
    return { rows: await commands[command](args) };
  } catch (error) {
    return { failure: { code: error.code || '', message: String(error.message || error) } };
  }
}
