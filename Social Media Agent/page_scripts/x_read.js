async ({ command, args }) => {
  // Reads X through X's own web API from inside x.com, the way x.com's own pages do: with the web app's
  // token, the session cookies and the ct0 cookie as anti-forgery header. Ported from OpenCLI 1.8.7
  // clis/twitter (profile.js, user-timeline.js, tweets.js, search.js, thread.js, shared.js; see third_party/NOTICE).

  // The token x.com's own web app sends with every request; it is public, not a secret.
  const WEB_APP_TOKEN = 'AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA';
  // Tweets asked for per page, and pages read at most per call.
  const PAGE_SIZE = 20;
  const MAX_PAGES = 3;

  const TIMELINE_FEATURES = {
    rweb_video_screen_enabled: true,
    rweb_cashtags_enabled: true,
    profile_label_improvements_pcf_label_in_post_enabled: true,
    responsive_web_profile_redirect_enabled: true,
    rweb_tipjar_consumption_enabled: true,
    verified_phone_label_enabled: false,
    creator_subscriptions_tweet_preview_api_enabled: true,
    responsive_web_graphql_timeline_navigation_enabled: true,
    responsive_web_graphql_skip_user_profile_image_extensions_enabled: false,
    premium_content_api_read_enabled: false,
    communities_web_enable_tweet_community_results_fetch: true,
    c9s_tweet_anatomy_moderator_badge_enabled: true,
    responsive_web_grok_analyze_button_fetch_trends_enabled: false,
    responsive_web_grok_analyze_post_followups_enabled: true,
    rweb_cashtags_composer_attachment_enabled: true,
    responsive_web_jetfuel_frame: true,
    responsive_web_grok_share_attachment_enabled: true,
    responsive_web_grok_annotations_enabled: true,
    articles_preview_enabled: true,
    responsive_web_edit_tweet_api_enabled: true,
    graphql_is_translatable_rweb_tweet_is_translatable_enabled: true,
    view_counts_everywhere_api_enabled: true,
    longform_notetweets_consumption_enabled: true,
    responsive_web_twitter_article_tweet_consumption_enabled: true,
    content_disclosure_indicator_enabled: true,
    content_disclosure_ai_generated_indicator_enabled: true,
    responsive_web_grok_show_grok_translated_post: false,
    responsive_web_grok_analysis_button_from_backend: true,
    post_ctas_fetch_enabled: false,
    freedom_of_speech_not_reach_fetch_enabled: true,
    standardized_nudges_misinfo: true,
    tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled: true,
    longform_notetweets_rich_text_read_enabled: true,
    longform_notetweets_inline_media_enabled: true,
    responsive_web_grok_image_annotation_enabled: true,
    responsive_web_grok_imagine_annotation_enabled: true,
    responsive_web_grok_community_note_auto_translation_is_enabled: false,
    responsive_web_enhance_cards_enabled: false,
  };
  const TIMELINE_FIELD_TOGGLES = {
    withPayments: true,
    withAuxiliaryUserLabels: true,
    withArticleRichContentState: true,
    withArticlePlainText: true,
    withArticleSummaryText: true,
    withArticleVoiceOver: true,
    withGrokAnalyze: true,
    withDisallowedReplyControls: true,
  };
  // Each web API operation the reads use: its query id and the feature flags X expects with it.
  const OPERATIONS = {
    UserByScreenName: {
      queryId: 'IGgvgiOx4QZndDHuD3x9TQ',
      features: {
        hidden_profile_subscriptions_enabled: true,
        profile_label_improvements_pcf_label_in_post_enabled: true,
        responsive_web_profile_redirect_enabled: true,
        rweb_tipjar_consumption_enabled: true,
        responsive_web_graphql_exclude_directive_enabled: true,
        verified_phone_label_enabled: false,
        subscriptions_verification_info_is_identity_verified_enabled: true,
        subscriptions_verification_info_verified_since_enabled: true,
        highlights_tweets_tab_ui_enabled: true,
        responsive_web_twitter_article_notes_tab_enabled: true,
        subscriptions_feature_can_gift_premium: true,
        creator_subscriptions_tweet_preview_api_enabled: true,
        responsive_web_graphql_skip_user_profile_image_extensions_enabled: false,
        responsive_web_graphql_timeline_navigation_enabled: true,
      },
      fieldToggles: { withPayments: true, withAuxiliaryUserLabels: true },
    },
    UserTweets: {
      queryId: 'lrMzG9qPQHpqJdP3AbM-bQ',
      features: { ...TIMELINE_FEATURES, payments_enabled: false, tweet_awards_web_tipping_enabled: false },
      fieldToggles: TIMELINE_FIELD_TOGGLES,
    },
    SearchTimeline: {
      queryId: 'Yw6L66Pw54NHKuq4Dp7b4Q',
      method: 'POST',
      features: TIMELINE_FEATURES,
      fieldToggles: TIMELINE_FIELD_TOGGLES,
    },
    TweetDetail: {
      queryId: 'nBS-WpgA6ZG0CyNHD517JQ',
      features: {
        responsive_web_graphql_exclude_directive_enabled: true,
        verified_phone_label_enabled: false,
        creator_subscriptions_tweet_preview_api_enabled: true,
        responsive_web_graphql_timeline_navigation_enabled: true,
        responsive_web_graphql_skip_user_profile_image_extensions_enabled: false,
        longform_notetweets_consumption_enabled: true,
        longform_notetweets_rich_text_read_enabled: true,
        longform_notetweets_inline_media_enabled: true,
        freedom_of_speech_not_reach_fetch_enabled: true,
        view_counts_everywhere_api_enabled: true,
      },
      fieldToggles: { withArticleRichContentState: true, withArticlePlainText: false },
    },
  };

  function failure(message, code) {
    const error = new Error(message);
    error.code = code;
    return error;
  }

  function csrfToken() {
    const match = document.cookie.match(/(?:^|;\s*)ct0=([^;]+)/);
    if (!match) throw failure('the session has no ct0 cookie', 'AUTH_REQUIRED');
    return match[1];
  }

  function request(name, operation, variables) {
    const url = `/i/api/graphql/${operation.queryId}/${name}`;
    const payload = { variables, features: operation.features, fieldToggles: operation.fieldToggles };
    const headers = {
      authorization: 'Bearer ' + WEB_APP_TOKEN,
      'x-csrf-token': csrfToken(),
      'x-twitter-auth-type': 'OAuth2Session',
      'x-twitter-active-user': 'yes',
    };
    if (operation.method === 'POST') {
      return fetch(url, {
        method: 'POST',
        credentials: 'include',
        headers: { ...headers, 'content-type': 'application/json' },
        body: JSON.stringify(payload),
      });
    }
    const query = Object.entries(payload).map(([key, value]) => `${key}=${encodeURIComponent(JSON.stringify(value))}`);
    return fetch(`${url}?${query.join('&')}`, { credentials: 'include', headers });
  }

  // X renames an operation's query id when it updates its website; the old id then answers 400 or 404.
  async function graphql(name, variables) {
    let response = await request(name, OPERATIONS[name], variables);
    if (response.status === 400 || response.status === 404) {
      const current = await currentOperation(name);
      if (current) response = await request(name, current, variables);
    }
    return answerData(response, name);
  }

  async function answerData(response, name) {
    if (response.status === 401 || response.status === 403) {
      throw failure(`X answered HTTP ${response.status} to ${name}`, 'AUTH_REQUIRED');
    }
    if (response.status === 429) throw failure(`X answered HTTP 429 to ${name}`, 'RATE_LIMITED');
    if (!response.ok) throw failure(`X answered HTTP ${response.status} to ${name}; its website may have changed`);
    let body;
    try {
      body = await response.json();
    } catch {
      throw failure(`X answered ${name} with a page instead of data`);
    }
    if (!body?.data && body?.errors?.length) throw failure(String(body.errors[0].message || 'X reported an error'));
    return body?.data || {};
  }

  // The operation's current query id, and the flags X now expects, from X's own website scripts on the page.
  async function currentOperation(name) {
    const scripts = new Set([...document.scripts].map((script) => script.src)
      .concat(performance.getEntriesByType('resource').map((entry) => entry.name)));
    for (const url of scripts) {
      if (!url.includes('/client-web/') || !url.endsWith('.js')) continue;
      try {
        const operation = operationIn(await (await fetch(url)).text(), name);
        if (operation) return operation;
      } catch {
        // A script that does not load is skipped; the next one may carry the operation.
      }
    }
    return null;
  }

  function operationIn(text, name) {
    const found = text.match(new RegExp(`queryId:"([A-Za-z0-9_-]+)"[^}]{0,400}operationName:"${name}"`))
      || text.match(new RegExp(`operationName:"${name}"[^}]{0,400}queryId:"([A-Za-z0-9_-]+)"`));
    if (!found) return null;
    const around = text.slice(Math.max(0, found.index - 500), found.index + 1500);
    const flags = (list) => Object.fromEntries(
      [...(around.match(new RegExp(`${list}:\\[([^\\]]*)\\]`))?.[1] || '').matchAll(/"([^"]+)"/g)].map((key) => [key[1], true]),
    );
    const known = OPERATIONS[name];
    const features = flags('featureSwitches');
    const fieldToggles = flags('fieldToggles');
    return {
      ...known,
      queryId: found[1],
      // Without the lists the built-in flags stay: X answers 400 to an empty list.
      features: Object.keys(features).length ? features : known.features,
      fieldToggles: Object.keys(fieldToggles).length ? fieldToggles : known.fieldToggles,
    };
  }

  function isoDate(value) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? '' : date.toISOString();
  }

  async function account(username) {
    const data = await graphql('UserByScreenName', { screen_name: username, withSafetyModeUserFields: true });
    const user = data.user?.result;
    if (!user?.rest_id || user.__typename === 'UserUnavailable') throw failure(`no account @${username}`, 'NOT_FOUND');
    return user;
  }

  function toProfile(user) {
    const core = user.core || {};
    const legacy = user.legacy || {};
    const username = core.screen_name || legacy.screen_name;
    return {
      username,
      name: core.name || legacy.name || '',
      bio: user.profile_bio?.description || legacy.description || '',
      location: user.location?.location || legacy.location || '',
      website: user.website?.url || legacy.entities?.url?.urls?.[0]?.expanded_url || '',
      followers: user.relationship_counts?.followers ?? legacy.followers_count ?? 0,
      following: user.relationship_counts?.following ?? legacy.friends_count ?? 0,
      tweets: user.tweet_counts?.tweets ?? legacy.statuses_count ?? 0,
      likes: user.action_counts?.favorites_count ?? legacy.favourites_count ?? 0,
      verified: Boolean(user.is_blue_verified || user.verification?.verified || legacy.verified),
      joined: isoDate(core.created_at || legacy.created_at),
      url: 'https://x.com/' + username,
    };
  }

  function media(legacy) {
    const items = legacy.extended_entities?.media || legacy.entities?.media || [];
    return items.filter(Boolean).map((item) => {
      if (item.type !== 'video' && item.type !== 'animated_gif') return { type: 'photo', url: item.media_url_https };
      const best = (item.video_info?.variants || [])
        .filter((variant) => variant.content_type === 'video/mp4')
        .sort((a, b) => (b.bitrate || 0) - (a.bitrate || 0))[0];
      return { type: item.type, url: best?.url || item.media_url_https };
    }).filter((item) => item.url);
  }

  function toTweet(result) {
    // Tweets with visibility limits come wrapped in a "tweet" field.
    const tweet = result.tweet || result;
    const legacy = tweet.legacy || {};
    const user = tweet.core?.user_results?.result || {};
    const author = user.core?.screen_name || user.legacy?.screen_name || '';
    const quoted = tweet.quoted_status_result?.result;
    const quotedId = (quoted?.tweet || quoted)?.rest_id;
    return {
      id: tweet.rest_id,
      url: `https://x.com/${author || 'i'}/status/${tweet.rest_id}`,
      author,
      name: user.core?.name || user.legacy?.name || '',
      text: tweet.note_tweet?.note_tweet_results?.result?.text || legacy.full_text || '',
      posted_at: isoDate(legacy.created_at),
      likes: legacy.favorite_count || 0,
      retweets: legacy.retweet_count || 0,
      replies: legacy.reply_count || 0,
      views: Number(tweet.views?.count) || 0,
      is_retweet: Boolean(legacy.retweeted_status_result || legacy.full_text?.startsWith('RT @')),
      in_reply_to: legacy.in_reply_to_status_id_str || '',
      media: media(legacy),
      quoted_tweet_url: quotedId ? `https://x.com/i/status/${quotedId}` : '',
    };
  }

  // X nests tweets and the next-page cursor at different depths per operation, so they are found by shape.
  // The pinned tweet is not part of a timeline's order and is left out.
  function timelinePage(data, seen) {
    const tweets = [];
    let next = null;
    const visit = (node) => {
      if (!node || typeof node !== 'object' || node.type === 'TimelinePinEntry') return;
      const result = node.tweet_results?.result;
      if (result) {
        const tweet = toTweet(result);
        if (tweet.id && !seen.has(tweet.id)) {
          seen.add(tweet.id);
          tweets.push(tweet);
        }
      }
      const isCursor = node.entryType === 'TimelineTimelineCursor' || node.__typename === 'TimelineTimelineCursor';
      if (isCursor && (node.cursorType === 'Bottom' || node.cursorType === 'ShowMore') && node.value) next = node.value;
      Object.values(node).forEach(visit);
    };
    visit(data);
    return { tweets, next };
  }

  async function readPages(name, variablesFor, limit) {
    const seen = new Set();
    const tweets = [];
    let cursor;
    for (let page = 0; page < MAX_PAGES && tweets.length < limit; page++) {
      const found = timelinePage(await graphql(name, variablesFor(cursor)), seen);
      tweets.push(...found.tweets);
      if (!found.next || found.next === cursor) break;
      cursor = found.next;
    }
    return tweets.slice(0, limit);
  }

  const commands = {
    async profile({ username }) {
      return [toProfile(await account(username))];
    },

    async tweets({ username, limit }) {
      const user = await account(username);
      return readPages('UserTweets', (cursor) => ({
        userId: user.rest_id,
        count: PAGE_SIZE,
        includePromotedContent: false,
        withQuickPromoteEligibilityTweetFields: true,
        withVoice: true,
        cursor,
      }), limit);
    },

    search({ query, limit }) {
      return readPages('SearchTimeline', (cursor) => ({
        rawQuery: query,
        count: PAGE_SIZE,
        querySource: 'typed_query',
        product: 'Top',
        cursor,
      }), limit);
    },

    async thread({ tweet_id: tweetId, limit }) {
      const tweets = await readPages('TweetDetail', (cursor) => ({
        focalTweetId: tweetId,
        referrer: 'tweet',
        with_rux_injections: false,
        includePromotedContent: false,
        rankingMode: 'Recency',
        withCommunity: true,
        withQuickPromoteEligibilityTweetFields: true,
        withBirdwatchNotes: true,
        withVoice: true,
        cursor,
      }), limit);
      if (!tweets.length) throw failure(`no tweet ${tweetId}`, 'NOT_FOUND');
      return tweets;
    },
  };

  try {
    return { rows: await commands[command](args) };
  } catch (error) {
    return { failure: { code: error.code || '', message: String(error.message || error) } };
  }
}
